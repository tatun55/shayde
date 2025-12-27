"""Route interception for Playwright."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Route
    from shayde.config.schema import ShaydeConfig

logger = logging.getLogger(__name__)


class RouteInterceptor:
    """Intercepts and redirects dev server requests.

    When using the proxy, this redirects requests from localhost/0.0.0.0
    to host.docker.internal where the proxy is accessible.
    """

    def __init__(self, config: ShaydeConfig):
        self.config = config
        self.proxy_port = config.proxy.port

        # Patterns to intercept (localhost variants → host.docker.internal)
        self._patterns = [
            # IPv6 localhost
            (re.compile(r"(https?://)\[::1\](:\d+)(.*)"), r"\1host.docker.internal\2\3"),
            # localhost
            (re.compile(r"(https?://)localhost(:\d+)(.*)"), r"\1host.docker.internal\2\3"),
            # 127.0.0.1
            (re.compile(r"(https?://)127\.0\.0\.1(:\d+)(.*)"), r"\1host.docker.internal\2\3"),
            # 0.0.0.0 (Vite uses this)
            (re.compile(r"(https?://)0\.0\.0\.0(:\d+)(.*)"), r"\1host.docker.internal\2\3"),
        ]

    async def handle_route(self, route: Route) -> None:
        """Handle route interception."""
        url = route.request.url

        for pattern, replacement in self._patterns:
            if pattern.match(url):
                new_url = pattern.sub(replacement, url)

                # If proxy is enabled, redirect Vite port to proxy port
                if self.config.proxy.enabled and self.config.proxy.vite_port:
                    vite_port = self.config.proxy.vite_port
                    new_url = new_url.replace(
                        f":{vite_port}",
                        f":{self.proxy_port}",
                    )

                logger.debug(f"Redirecting: {url} -> {new_url}")
                await route.continue_(url=new_url)
                return

        await route.continue_()


def create_route_handler(config: ShaydeConfig):
    """Create a route handler function for Playwright."""
    interceptor = RouteInterceptor(config)
    return interceptor.handle_route
