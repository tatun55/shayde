"""Screenshot capture logic."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union
from urllib.parse import urljoin, urlparse

if TYPE_CHECKING:
    from playwright.async_api import Page
    from playcap.config.schema import PlayCapConfig, ViewportConfig

logger = logging.getLogger(__name__)


def resolve_url(url_or_path: str, base_url: Optional[str]) -> str:
    """Resolve URL or path to full URL."""
    if url_or_path.startswith(("http://", "https://")):
        return url_or_path

    if base_url:
        return urljoin(base_url, url_or_path)

    # Assume localhost if no base URL
    return f"http://localhost{url_or_path}"


def generate_filename(
    url: str,
    name: Optional[str] = None,
    viewport_name: Optional[str] = None,
    platform_suffix: Optional[str] = None,
    pattern: str = "{name}_{date}_{time}.png",
    date_format: str = "%Y-%m-%d",
    time_format: str = "%H%M%S",
) -> str:
    """Generate screenshot filename."""
    now = datetime.now()

    if name:
        safe_name = re.sub(r"[^\w\-]", "_", name)
    else:
        parsed = urlparse(url)
        path = parsed.path.strip("/") or "home"
        safe_name = re.sub(r"[^\w\-]", "_", path)

    if viewport_name:
        safe_name = f"{safe_name}_{viewport_name}"

    if platform_suffix:
        safe_name = f"{safe_name}_{platform_suffix}"

    return pattern.format(
        name=safe_name,
        date=now.strftime(date_format),
        time=now.strftime(time_format),
    )


async def capture_screenshot(
    page: Page,
    url: str,
    output_path: Path,
    full_page: bool = False,
    wait_until: str = "networkidle",
    wait_after: int = 0,
    wait_for_selector: Optional[str] = None,
) -> Path:
    """Capture a screenshot of a page.

    Args:
        page: Playwright page instance
        url: URL to navigate to
        output_path: Path to save screenshot
        full_page: Capture full page instead of viewport
        wait_until: Navigation wait condition
        wait_after: Additional wait time in ms after page load
        wait_for_selector: CSS selector to wait for before capture

    Returns:
        Path to saved screenshot
    """
    logger.info(f"Navigating to {url}")
    await page.goto(url, wait_until=wait_until)

    if wait_for_selector:
        logger.debug(f"Waiting for selector: {wait_for_selector}")
        await page.wait_for_selector(wait_for_selector, timeout=10000)

    if wait_after > 0:
        logger.debug(f"Waiting {wait_after}ms after page load")
        await page.wait_for_timeout(wait_after)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Capturing screenshot to {output_path}")
    await page.screenshot(path=str(output_path), full_page=full_page)

    return output_path


class CaptureSession:
    """Manages a capture session with browser and proxy."""

    def __init__(self, config: "PlayCapConfig", platform: Optional[str] = None):
        self.config = config
        self._platform = platform
        self._browser_manager = None
        self._proxy_manager = None
        self._docker_manager = None
        self._authenticated_context = None

    def get_platform_css(self) -> str:
        """Get CSS for current platform's fonts."""
        from playcap.docker.manager import PLATFORM_CSS
        platform = self._platform or self.config.fonts.platform
        return PLATFORM_CSS.get(platform, PLATFORM_CSS["neutral"])

    async def _inject_platform_css(self, page) -> None:
        """Inject platform-specific font CSS into the page."""
        css = self.get_platform_css()
        await page.add_style_tag(content=css)

    async def setup(self) -> None:
        """Set up capture session (Docker, proxy, browser)."""
        from playcap.docker.manager import DockerManager
        from playcap.proxy.manager import ProxyManager
        from playcap.core.browser import BrowserManager
        from playcap.core.routes import create_route_handler

        # Start Docker container
        self._docker_manager = DockerManager(self.config)
        if self._platform:
            self._docker_manager.set_platform(self._platform)
        if self.config.docker.auto_start:
            if not self._docker_manager.start():
                raise RuntimeError("Failed to start Docker container")

        # Start proxy if enabled
        if self.config.proxy.enabled:
            self._proxy_manager = ProxyManager(self.config)
            await self._proxy_manager.start()

        # Connect to browser
        ws_url = self._docker_manager.get_ws_url()
        self._browser_manager = BrowserManager(ws_url)
        await self._browser_manager.connect()

    async def teardown(self) -> None:
        """Tear down capture session."""
        if self._authenticated_context:
            await self._authenticated_context.close()
            self._authenticated_context = None

        if self._browser_manager:
            await self._browser_manager.disconnect()

        if self._proxy_manager:
            await self._proxy_manager.stop()

        if self._docker_manager and self.config.docker.auto_stop:
            self._docker_manager.stop()

    async def login(
        self,
        email: str,
        password: str,
        login_url: Optional[str] = None,
    ) -> bool:
        """Login to the application and store authenticated context.

        Args:
            email: Email/username
            password: Password
            login_url: Login page URL (defaults to /login)

        Returns:
            True if login was successful
        """
        from playcap.core.auth import login_with_form
        from playcap.core.routes import create_route_handler

        # Resolve login URL
        if login_url is None:
            login_url = resolve_url("/login", self.config.app.base_url)
        else:
            login_url = resolve_url(login_url, self.config.app.base_url)

        # Create a new context for authenticated session
        browser = await self._browser_manager.connect()
        self._authenticated_context = await browser.new_context()
        page = await self._authenticated_context.new_page()

        # Set up route interception
        route_handler = create_route_handler(self.config)
        await page.route("**/*", route_handler)

        # Perform login
        success = await login_with_form(
            page=page,
            login_url=login_url,
            email=email,
            password=password,
        )

        if not success:
            await self._authenticated_context.close()
            self._authenticated_context = None

        return success

    async def capture(
        self,
        url_or_path: str,
        name: Optional[str] = None,
        viewport: Optional[Union[str, "ViewportConfig"]] = None,
        full_page: Optional[bool] = None,
        wait_for: Optional[str] = None,
        output_dir: Optional[Path] = None,
        platform_suffix: Optional[str] = None,
    ) -> Path:
        """Capture a single screenshot.

        Args:
            url_or_path: URL or path to capture
            name: Custom filename prefix
            viewport: Viewport name or config
            full_page: Capture full page
            wait_for: CSS selector to wait for
            output_dir: Output directory override
            platform_suffix: Platform name to add to filename

        Returns:
            Path to saved screenshot
        """
        from playcap.core.routes import create_route_handler

        # Resolve URL
        url = resolve_url(url_or_path, self.config.app.base_url)

        # Resolve viewport
        viewport_config = None
        viewport_name = None
        if isinstance(viewport, str):
            viewport_name = viewport
            viewport_config = self.config.viewports.get(viewport)
        elif viewport:
            viewport_config = viewport
        else:
            viewport_name = self.config.capture.default_viewport
            viewport_config = self.config.viewports.get(viewport_name)

        # Use authenticated context if available, otherwise create new page
        if self._authenticated_context:
            # Create page in authenticated context
            page = await self._authenticated_context.new_page()
            if viewport_config:
                await page.set_viewport_size({
                    "width": viewport_config.width,
                    "height": viewport_config.height,
                })
        else:
            # Create page with viewport
            page = await self._browser_manager.new_page(viewport_config)

        # Set up route interception
        route_handler = create_route_handler(self.config)
        await page.route("**/*", route_handler)

        try:
            # Generate output path (include platform_suffix if specified)
            output_directory = output_dir or Path.cwd() / self.config.output.directory
            filename = generate_filename(
                url,
                name=name,
                viewport_name=viewport_name,
                platform_suffix=platform_suffix,
                pattern=self.config.output.filename_pattern,
                date_format=self.config.output.date_format,
                time_format=self.config.output.time_format,
            )
            output_path = output_directory / filename

            # Navigate to page
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until=self.config.capture.wait_until)

            # Inject platform-specific CSS for fonts
            if self._platform:
                await self._inject_platform_css(page)

            # Wait for selector if specified
            if wait_for:
                logger.debug(f"Waiting for selector: {wait_for}")
                await page.wait_for_selector(wait_for, timeout=10000)

            # Additional wait after page load
            if self.config.capture.wait_after > 0:
                logger.debug(f"Waiting {self.config.capture.wait_after}ms after page load")
                await page.wait_for_timeout(self.config.capture.wait_after)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Capture screenshot
            logger.info(f"Capturing screenshot to {output_path}")
            await page.screenshot(
                path=str(output_path),
                full_page=full_page if full_page is not None else self.config.capture.full_page,
            )

            return output_path

        finally:
            # Only close context if not using authenticated context
            if not self._authenticated_context:
                await page.context.close()
            else:
                await page.close()

    async def __aenter__(self) -> "CaptureSession":
        """Async context manager entry."""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.teardown()
