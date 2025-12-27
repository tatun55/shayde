"""Proxy lifecycle manager."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import TYPE_CHECKING

from shayde.proxy.server import DevServerProxy

if TYPE_CHECKING:
    from shayde.config.schema import ShaydeConfig

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages the proxy server lifecycle."""

    def __init__(self, config: ShaydeConfig):
        self.config = config
        self.proxy: DevServerProxy | None = None
        self._task: asyncio.Task | None = None

    def _create_proxy(self) -> DevServerProxy:
        """Create proxy instance from config."""
        return DevServerProxy(
            target_host="localhost",
            target_port=self.config.proxy.vite_port or 5173,
            listen_host="0.0.0.0",
            listen_port=self.config.proxy.port,
            websocket=self.config.proxy.websocket,
        )

    async def start(self) -> DevServerProxy:
        """Start the proxy server."""
        if self.proxy and self.proxy.is_running:
            return self.proxy

        self.proxy = self._create_proxy()
        await self.proxy.start()
        return self.proxy

    async def stop(self) -> None:
        """Stop the proxy server."""
        if self.proxy:
            await self.proxy.stop()
            self.proxy = None

    async def __aenter__(self) -> DevServerProxy:
        """Async context manager entry."""
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


async def run_proxy_standalone(config: ShaydeConfig) -> None:
    """Run proxy as standalone server (for debugging)."""
    manager = ProxyManager(config)

    loop = asyncio.get_event_loop()

    # Handle shutdown signals
    def shutdown_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(manager.stop())
        loop.stop()

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    try:
        proxy = await manager.start()
        print(f"Proxy running: {proxy.listen_url} -> {proxy.target_url}")
        print("Press Ctrl+C to stop")

        # Keep running
        while proxy.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        await manager.stop()
