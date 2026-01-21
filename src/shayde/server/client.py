"""Shayde HTTP client for communicating with server."""

from __future__ import annotations

import asyncio
import socket
from typing import Any, Dict, Optional

import aiohttp

from shayde.server.app import DEFAULT_PORT, is_running


class ShaydeClient:
    """HTTP client for Shayde server."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    @staticmethod
    def server_available(port: int = DEFAULT_PORT) -> bool:
        """Check if server is available (quick socket check)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def health(self) -> Dict[str, Any]:
        """Check server health."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/health") as resp:
                return await resp.json()

    async def capture(
        self,
        url: str,
        output: str,
        viewport: Optional[Dict[str, int]] = None,
        full_page: bool = False,
        wait_until: str = "networkidle",
    ) -> Dict[str, Any]:
        """Capture screenshot via server."""
        data = {
            "url": url,
            "output": output,
            "full_page": full_page,
            "wait_until": wait_until,
        }
        if viewport:
            data["viewport"] = viewport

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/capture", json=data) as resp:
                return await resp.json()

    async def stop(self) -> Dict[str, Any]:
        """Request server to stop."""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/stop") as resp:
                return await resp.json()

    def capture_sync(
        self,
        url: str,
        output: str,
        viewport: Optional[Dict[str, int]] = None,
        full_page: bool = False,
        wait_until: str = "networkidle",
    ) -> Dict[str, Any]:
        """Synchronous capture."""
        return asyncio.run(self.capture(url, output, viewport, full_page, wait_until))

    def health_sync(self) -> Dict[str, Any]:
        """Synchronous health check."""
        return asyncio.run(self.health())

    def stop_sync(self) -> Dict[str, Any]:
        """Synchronous stop."""
        return asyncio.run(self.stop())
