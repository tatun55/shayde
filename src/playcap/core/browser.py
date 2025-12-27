"""Playwright browser connection and management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncContextManager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

if TYPE_CHECKING:
    from playcap.config.schema import PlayCapConfig, ViewportConfig

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser connection via WebSocket."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._playwright = None
        self._browser: Browser | None = None

    async def connect(self) -> Browser:
        """Connect to Playwright WebSocket server."""
        if self._browser:
            return self._browser

        logger.info(f"Connecting to Playwright at {self.ws_url}")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect(self.ws_url)
        logger.info("Connected to Playwright")
        return self._browser

    async def disconnect(self) -> None:
        """Disconnect from Playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Disconnected from Playwright")

    async def new_page(
        self,
        viewport: ViewportConfig | None = None,
    ) -> Page:
        """Create a new page with specified viewport."""
        if not self._browser:
            await self.connect()

        viewport_dict = None
        if viewport:
            viewport_dict = {
                "width": viewport.width,
                "height": viewport.height,
            }

        context = await self._browser.new_context(
            viewport=viewport_dict,
            device_scale_factor=viewport.device_scale_factor if viewport else 1,
        )
        page = await context.new_page()
        return page

    async def __aenter__(self) -> "BrowserManager":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
