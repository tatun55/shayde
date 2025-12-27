"""Authentication support for Shayde."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def login_with_form(
    page: Page,
    login_url: str,
    email: str,
    password: str,
    email_field: str = 'input[type="email"], input[name="email"]',
    password_field: str = 'input[type="password"], input[name="password"]',
    submit_button: str = 'button[type="submit"]',
    success_indicator: Optional[str] = None,
    wait_after_login: int = 2000,
) -> bool:
    """Login to the application using form-based authentication.

    Args:
        page: Playwright page instance
        login_url: URL of the login page
        email: Email/username to use
        password: Password to use
        email_field: CSS selector for email input
        password_field: CSS selector for password input
        submit_button: CSS selector for submit button
        success_indicator: CSS selector to wait for after login (optional)
        wait_after_login: Time to wait after login in ms

    Returns:
        True if login was successful
    """
    logger.info(f"Logging in at {login_url}")

    # Navigate to login page
    await page.goto(login_url, wait_until="networkidle")

    # Fill in credentials
    logger.debug(f"Filling email field: {email_field}")
    await page.fill(email_field, email)

    logger.debug(f"Filling password field: {password_field}")
    await page.fill(password_field, password)

    # Click submit
    logger.debug(f"Clicking submit button: {submit_button}")
    await page.click(submit_button)

    # Wait for navigation or success indicator
    if success_indicator:
        try:
            await page.wait_for_selector(success_indicator, timeout=10000)
            logger.info("Login successful (success indicator found)")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    else:
        # Wait for navigation to complete
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(wait_after_login)

        # Check if we're still on login page (login failed)
        current_url = page.url
        if "/login" in current_url.lower():
            logger.warning("Login may have failed (still on login page)")
            return False

        logger.info(f"Login successful, redirected to {current_url}")
        return True
