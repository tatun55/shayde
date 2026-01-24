"""Playwright action executors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of an action execution."""
    success: bool
    action_type: str
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict] = None


class ActionExecutor:
    """Execute Playwright actions from YAML definitions."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url

    async def execute(self, page: "Page", action: Union[dict, list[dict]]) -> ActionResult:
        """Execute action(s) defined in YAML.

        Args:
            page: Playwright page
            action: Action definition (dict or list of dicts)

        Returns:
            ActionResult
        """
        if action is None:
            return ActionResult(success=True, action_type="none", message="No action")

        if isinstance(action, list):
            return await self._execute_multi(page, action)

        return await self._execute_single(page, action)

    async def _execute_single(self, page: "Page", action: dict) -> ActionResult:
        """Execute a single action."""
        # Determine action type and execute
        if "goto" in action:
            return await self.goto(page, action["goto"], action.get("wait"))

        if "fill" in action:
            fill_data = action["fill"]
            if isinstance(fill_data, dict):
                return await self.fill(page, fill_data["selector"], fill_data["value"])
            # Simple fill: { fill: selector }
            return ActionResult(
                success=False,
                action_type="fill",
                error="Invalid fill format. Use: fill: { selector: '...', value: '...' }",
            )

        if "click" in action:
            return await self.click(page, action["click"], action.get("wait"))

        if "select" in action:
            select_data = action["select"]
            return await self.select(page, select_data["selector"], select_data["value"])

        if "upload" in action:
            upload_data = action["upload"]
            return await self.upload(page, upload_data["selector"], upload_data["file"])

        if "clear" in action:
            return await self.clear(page, action["clear"])

        if "type" in action:
            type_data = action["type"]
            return await self.type_text(
                page,
                type_data["selector"],
                type_data["value"],
                type_data.get("delay", 0),
            )

        if "login" in action:
            # Login shortcut - will be handled by session
            return ActionResult(
                success=True,
                action_type="login",
                message=f"Login requested for account: {action['login']}",
                data={"account": action["login"]},
            )

        if "logout" in action:
            return await self.logout(page)

        if "wait" in action:
            return await self.wait(page, action["wait"])

        if "accept_dialog" in action:
            return await self.handle_dialog(page, accept=True)

        if "dismiss_dialog" in action:
            return await self.handle_dialog(page, accept=False)

        return ActionResult(
            success=False,
            action_type="unknown",
            error=f"Unknown action: {list(action.keys())}",
        )

    async def _execute_multi(self, page: "Page", actions: list[dict]) -> ActionResult:
        """Execute multiple actions in sequence."""
        results = []
        for i, action in enumerate(actions):
            result = await self._execute_single(page, action)
            results.append(result)
            if not result.success:
                return ActionResult(
                    success=False,
                    action_type="multi",
                    error=f"Action {i + 1} failed: {result.error}",
                    data={"results": results},
                )

        return ActionResult(
            success=True,
            action_type="multi",
            message=f"Executed {len(actions)} actions",
            data={"results": results},
        )

    async def goto(
        self, page: "Page", url: str, wait_for: Optional[str] = None
    ) -> ActionResult:
        """Navigate to URL.

        Args:
            page: Playwright page
            url: URL or path to navigate to
            wait_for: Optional selector or URL to wait for after navigation
        """
        try:
            # Resolve URL
            if url.startswith(("/", "#")):
                if self.base_url:
                    full_url = f"{self.base_url.rstrip('/')}{url}"
                else:
                    full_url = f"http://localhost{url}"
            else:
                full_url = url

            logger.info(f"Navigating to {full_url}")
            await page.goto(full_url, wait_until="networkidle")

            # Wait for additional condition
            if wait_for:
                if wait_for.startswith("/"):
                    # Wait for URL
                    await page.wait_for_url(f"**{wait_for}*", timeout=10000)
                else:
                    # Wait for selector
                    await page.wait_for_selector(wait_for, timeout=10000)

            return ActionResult(
                success=True,
                action_type="goto",
                message=f"Navigated to {full_url}",
                data={"url": full_url, "current_url": page.url},
            )

        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return ActionResult(
                success=False,
                action_type="goto",
                error=str(e),
            )

    async def fill(self, page: "Page", selector: str, value: str) -> ActionResult:
        """Fill input field.

        Args:
            page: Playwright page
            selector: CSS selector
            value: Value to fill
        """
        try:
            logger.debug(f"Filling {selector} with '{value}'")
            await page.fill(selector, value)

            return ActionResult(
                success=True,
                action_type="fill",
                message=f"Filled {selector}",
                data={"selector": selector, "value": value},
            )

        except Exception as e:
            logger.error(f"Fill failed: {e}")
            return ActionResult(
                success=False,
                action_type="fill",
                error=str(e),
            )

    async def click(
        self, page: "Page", selector: str, wait_for: Optional[str] = None
    ) -> ActionResult:
        """Click element.

        Args:
            page: Playwright page
            selector: CSS selector or text selector (text=...)
            wait_for: Optional URL or selector to wait for after click
        """
        try:
            logger.debug(f"Clicking {selector}")
            await page.click(selector)

            # Wait for additional condition
            if wait_for:
                if wait_for.startswith("/"):
                    # Wait for URL
                    await page.wait_for_url(f"**{wait_for}*", timeout=10000)
                else:
                    # Wait for selector
                    await page.wait_for_selector(wait_for, timeout=10000)

            return ActionResult(
                success=True,
                action_type="click",
                message=f"Clicked {selector}",
                data={"selector": selector},
            )

        except Exception as e:
            logger.error(f"Click failed: {e}")
            return ActionResult(
                success=False,
                action_type="click",
                error=str(e),
            )

    async def select(self, page: "Page", selector: str, value: str) -> ActionResult:
        """Select option from dropdown.

        Args:
            page: Playwright page
            selector: CSS selector
            value: Option value or text
        """
        try:
            logger.debug(f"Selecting '{value}' in {selector}")
            await page.select_option(selector, value)

            return ActionResult(
                success=True,
                action_type="select",
                message=f"Selected '{value}' in {selector}",
                data={"selector": selector, "value": value},
            )

        except Exception as e:
            logger.error(f"Select failed: {e}")
            return ActionResult(
                success=False,
                action_type="select",
                error=str(e),
            )

    async def upload(self, page: "Page", selector: str, file_path: str) -> ActionResult:
        """Upload file.

        Args:
            page: Playwright page
            selector: CSS selector for file input
            file_path: Path to file (relative to scenario directory)
        """
        try:
            path = Path(file_path)
            if not path.is_absolute():
                # Resolve relative to current working directory
                path = Path.cwd() / path

            if not path.exists():
                return ActionResult(
                    success=False,
                    action_type="upload",
                    error=f"File not found: {path}",
                )

            logger.debug(f"Uploading {path} to {selector}")
            await page.set_input_files(selector, str(path))

            return ActionResult(
                success=True,
                action_type="upload",
                message=f"Uploaded {path.name}",
                data={"selector": selector, "file": str(path)},
            )

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return ActionResult(
                success=False,
                action_type="upload",
                error=str(e),
            )

    async def clear(self, page: "Page", selector: str) -> ActionResult:
        """Clear input field.

        Args:
            page: Playwright page
            selector: CSS selector
        """
        try:
            logger.debug(f"Clearing {selector}")
            await page.fill(selector, "")

            return ActionResult(
                success=True,
                action_type="clear",
                message=f"Cleared {selector}",
                data={"selector": selector},
            )

        except Exception as e:
            logger.error(f"Clear failed: {e}")
            return ActionResult(
                success=False,
                action_type="clear",
                error=str(e),
            )

    async def type_text(
        self, page: "Page", selector: str, value: str, delay: int = 0
    ) -> ActionResult:
        """Type text character by character.

        Args:
            page: Playwright page
            selector: CSS selector
            value: Text to type
            delay: Delay between keystrokes in ms
        """
        try:
            logger.debug(f"Typing into {selector}")
            await page.type(selector, value, delay=delay)

            return ActionResult(
                success=True,
                action_type="type",
                message=f"Typed into {selector}",
                data={"selector": selector, "value": value, "delay": delay},
            )

        except Exception as e:
            logger.error(f"Type failed: {e}")
            return ActionResult(
                success=False,
                action_type="type",
                error=str(e),
            )

    async def wait(self, page: "Page", target) -> ActionResult:
        """Wait for URL, selector, or duration.

        Args:
            page: Playwright page
            target: URL pattern (starts with /), CSS selector, or duration in ms (int)
        """
        import asyncio

        try:
            # If target is a number, wait for that duration
            if isinstance(target, (int, float)):
                logger.debug(f"Waiting for {target}ms")
                await asyncio.sleep(target / 1000)
                return ActionResult(
                    success=True,
                    action_type="wait",
                    message=f"Waited for {target}ms",
                    data={"duration_ms": target},
                )

            # String target: URL or selector
            if target.startswith("/"):
                logger.debug(f"Waiting for URL: {target}")
                await page.wait_for_url(f"**{target}*", timeout=10000)
            else:
                logger.debug(f"Waiting for selector: {target}")
                await page.wait_for_selector(target, timeout=10000)

            return ActionResult(
                success=True,
                action_type="wait",
                message=f"Waited for {target}",
                data={"target": target},
            )

        except Exception as e:
            logger.error(f"Wait failed: {e}")
            return ActionResult(
                success=False,
                action_type="wait",
                error=str(e),
            )

    async def logout(self, page: "Page") -> ActionResult:
        """Logout (clear cookies and storage).

        Args:
            page: Playwright page
        """
        try:
            logger.debug("Logging out (clearing cookies)")
            context = page.context
            await context.clear_cookies()

            return ActionResult(
                success=True,
                action_type="logout",
                message="Logged out (cookies cleared)",
            )

        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return ActionResult(
                success=False,
                action_type="logout",
                error=str(e),
            )

    async def handle_dialog(self, page: "Page", accept: bool = True) -> ActionResult:
        """Set up a one-time dialog handler.

        Args:
            page: Playwright page
            accept: True to accept, False to dismiss
        """
        import asyncio

        action_type = "accept_dialog" if accept else "dismiss_dialog"
        dialog_handled = asyncio.Event()
        dialog_info = {"type": None, "message": None}

        async def one_time_handler(dialog):
            dialog_info["type"] = dialog.type
            dialog_info["message"] = dialog.message
            if accept:
                await dialog.accept()
            else:
                await dialog.dismiss()
            dialog_handled.set()

        page.once("dialog", one_time_handler)

        try:
            # Wait for dialog with timeout
            await asyncio.wait_for(dialog_handled.wait(), timeout=10.0)
            logger.info(f"Dialog {action_type}: {dialog_info['type']} - {dialog_info['message']}")

            return ActionResult(
                success=True,
                action_type=action_type,
                message=f"Dialog {action_type}d: {dialog_info['message']}",
                data=dialog_info,
            )

        except asyncio.TimeoutError:
            logger.warning(f"No dialog appeared within timeout for {action_type}")
            return ActionResult(
                success=True,  # Not a failure, just no dialog
                action_type=action_type,
                message="No dialog appeared",
            )

        except Exception as e:
            logger.error(f"Dialog handling failed: {e}")
            return ActionResult(
                success=False,
                action_type=action_type,
                error=str(e),
            )
