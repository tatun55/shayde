"""Shayde HTTP server for persistent Playwright connection."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aiohttp import web
from playwright.async_api import async_playwright, Browser, Playwright

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9876
PID_FILE = Path("/tmp/shayde-server.pid")
SOCKET_FILE = Path("/tmp/shayde-server.sock")


class ShaydeServer:
    """HTTP server that maintains persistent Playwright connection."""

    def __init__(self, ws_url: str = "ws://localhost:3000", port: int = DEFAULT_PORT):
        self.ws_url = ws_url
        self.port = port
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

    async def _ensure_browser(self) -> Browser:
        """Ensure browser connection is established."""
        if self._browser is None or not self._browser.is_connected():
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect(self.ws_url)
            logger.info(f"Connected to Playwright at {self.ws_url}")
        return self._browser

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        try:
            browser = await self._ensure_browser()
            return web.json_response({
                "status": "ok",
                "browser_connected": browser.is_connected(),
            })
        except Exception as e:
            return web.json_response({
                "status": "error",
                "error": str(e),
            }, status=500)

    async def _handle_capture(self, request: web.Request) -> web.Response:
        """Screenshot capture endpoint."""
        try:
            data = await request.json()
            url = data.get("url")
            output = data.get("output", "/tmp/shayde-capture.png")
            viewport = data.get("viewport", {"width": 1920, "height": 1080})
            full_page = data.get("full_page", False)
            wait_until = data.get("wait_until", "networkidle")

            if not url:
                return web.json_response({"error": "url is required"}, status=400)

            browser = await self._ensure_browser()
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()

            try:
                await page.goto(url, wait_until=wait_until)
                await page.screenshot(path=output, full_page=full_page)
            finally:
                await context.close()

            return web.json_response({
                "status": "ok",
                "output": output,
            })
        except Exception as e:
            logger.exception("Capture failed")
            return web.json_response({
                "status": "error",
                "error": str(e),
            }, status=500)

    async def _handle_stop(self, request: web.Request) -> web.Response:
        """Stop server endpoint."""
        asyncio.create_task(self._shutdown())
        return web.json_response({"status": "stopping"})

    async def _shutdown(self) -> None:
        """Graceful shutdown."""
        await asyncio.sleep(0.5)  # Allow response to be sent
        if self._runner:
            await self._runner.cleanup()

    def _create_app(self) -> web.Application:
        """Create aiohttp application."""
        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_post("/capture", self._handle_capture)
        app.router.add_post("/stop", self._handle_stop)
        return app

    async def start(self) -> None:
        """Start the server."""
        self._app = self._create_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        logger.info(f"Shayde server started on http://127.0.0.1:{self.port}")

        # Pre-connect to browser
        try:
            await self._ensure_browser()
        except Exception as e:
            logger.warning(f"Could not pre-connect to browser: {e}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        if self._runner:
            await self._runner.cleanup()

        # Remove PID file
        if PID_FILE.exists():
            PID_FILE.unlink()

        logger.info("Shayde server stopped")

    async def run_forever(self) -> None:
        """Run server until interrupted."""
        await self.start()

        # Wait for shutdown signal
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def signal_handler():
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await stop_event.wait()
        await self.stop()


def run_server(ws_url: str = "ws://localhost:3000", port: int = DEFAULT_PORT) -> None:
    """Run the server (blocking)."""
    server = ShaydeServer(ws_url=ws_url, port=port)
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass


def get_pid() -> Optional[int]:
    """Get server PID if running."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # Clean up stale PID file
        PID_FILE.unlink(missing_ok=True)
        return None


def is_running() -> bool:
    """Check if server is running."""
    return get_pid() is not None
