"""HTTP/WebSocket proxy server for dev server access."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web, WSMsgType

if TYPE_CHECKING:
    from multidict import CIMultiDictProxy

logger = logging.getLogger(__name__)


# Headers that should not be forwarded
HOP_BY_HOP_HEADERS = frozenset([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
])


class DevServerProxy:
    """HTTP/WebSocket proxy for Vite/Webpack dev servers.

    This proxy allows Docker containers to access the host's dev server
    by listening on 0.0.0.0 and forwarding requests to localhost.
    """

    def __init__(
        self,
        target_host: str = "localhost",
        target_port: int = 5173,
        listen_host: str = "0.0.0.0",
        listen_port: int = 9999,
        websocket: bool = True,
    ):
        self.target_host = target_host
        self.target_port = target_port
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.websocket = websocket

        self.app = web.Application()
        self.app.router.add_route("*", "/{path:.*}", self.proxy_handler)
        self.runner: web.AppRunner | None = None
        self._running = False

    @property
    def target_url(self) -> str:
        """Get the target URL base."""
        return f"http://{self.target_host}:{self.target_port}"

    @property
    def listen_url(self) -> str:
        """Get the listen URL."""
        return f"http://{self.listen_host}:{self.listen_port}"

    def _filter_headers(
        self, headers: CIMultiDictProxy[str], for_response: bool = False
    ) -> dict[str, str]:
        """Filter hop-by-hop headers."""
        filtered = {}
        for name, value in headers.items():
            lower_name = name.lower()
            if lower_name in HOP_BY_HOP_HEADERS:
                continue
            # Don't forward host header to target
            if not for_response and lower_name == "host":
                continue
            filtered[name] = value
        return filtered

    async def proxy_handler(self, request: web.Request) -> web.Response | web.WebSocketResponse:
        """Handle incoming requests and proxy to target."""
        path = request.path
        if request.query_string:
            path = f"{path}?{request.query_string}"

        target_url = f"{self.target_url}{path}"

        logger.debug(f"Proxying {request.method} {request.path} -> {target_url}")

        # Handle WebSocket upgrade
        if (
            self.websocket
            and request.headers.get("Upgrade", "").lower() == "websocket"
        ):
            return await self._proxy_websocket(request, target_url)

        # Handle regular HTTP request
        return await self._proxy_http(request, target_url)

    async def _proxy_http(self, request: web.Request, target_url: str) -> web.Response:
        """Proxy HTTP request."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = self._filter_headers(request.headers)
                body = await request.read()

                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=body if body else None,
                    allow_redirects=False,
                ) as resp:
                    response_headers = self._filter_headers(resp.headers, for_response=True)
                    body = await resp.read()

                    return web.Response(
                        body=body,
                        status=resp.status,
                        headers=response_headers,
                    )

        except aiohttp.ClientConnectorError as e:
            logger.error(f"Failed to connect to {target_url}: {e}")
            return web.Response(
                text=f"Proxy error: Cannot connect to dev server at {self.target_url}",
                status=502,
            )

    async def _proxy_websocket(
        self, request: web.Request, target_url: str
    ) -> web.WebSocketResponse:
        """Proxy WebSocket connection for HMR."""
        ws_response = web.WebSocketResponse()
        await ws_response.prepare(request)

        ws_url = target_url.replace("http://", "ws://").replace("https://", "wss://")
        logger.debug(f"Proxying WebSocket to {ws_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws_target:
                    # Create tasks for bidirectional forwarding
                    async def forward_client_to_target():
                        try:
                            async for msg in ws_response:
                                if msg.type == WSMsgType.TEXT:
                                    await ws_target.send_str(msg.data)
                                elif msg.type == WSMsgType.BINARY:
                                    await ws_target.send_bytes(msg.data)
                                elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                    break
                        except Exception as e:
                            logger.debug(f"Client->Target forward ended: {e}")

                    async def forward_target_to_client():
                        try:
                            async for msg in ws_target:
                                if msg.type == WSMsgType.TEXT:
                                    await ws_response.send_str(msg.data)
                                elif msg.type == WSMsgType.BINARY:
                                    await ws_response.send_bytes(msg.data)
                                elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                    break
                        except Exception as e:
                            logger.debug(f"Target->Client forward ended: {e}")

                    # Run both directions concurrently
                    await asyncio.gather(
                        forward_client_to_target(),
                        forward_target_to_client(),
                        return_exceptions=True,
                    )

        except aiohttp.ClientConnectorError as e:
            logger.error(f"WebSocket connection failed: {e}")

        return ws_response

    async def start(self) -> None:
        """Start the proxy server."""
        if self._running:
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.listen_host, self.listen_port)
        await site.start()

        self._running = True
        logger.info(f"Proxy started: {self.listen_url} -> {self.target_url}")

    async def stop(self) -> None:
        """Stop the proxy server."""
        if not self._running:
            return

        if self.runner:
            await self.runner.cleanup()
            self.runner = None

        self._running = False
        logger.info("Proxy stopped")

    @property
    def is_running(self) -> bool:
        """Check if proxy is running."""
        return self._running
