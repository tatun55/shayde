"""Playwright assertion executors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from playwright.async_api import Page

from shayde.core.scenario.models import AssertionResult

logger = logging.getLogger(__name__)


class AssertionExecutor:
    """Execute assertions from YAML definitions."""

    async def verify(
        self, page: "Page", expect: Union[dict, list[dict]]
    ) -> list[AssertionResult]:
        """Verify expectation(s) defined in YAML.

        Args:
            page: Playwright page
            expect: Expectation definition (dict or list of dicts)

        Returns:
            List of AssertionResult
        """
        if expect is None:
            return []

        if isinstance(expect, list):
            results = []
            for exp in expect:
                results.extend(await self._verify_single(page, exp))
            return results

        return await self._verify_single(page, expect)

    async def _verify_single(self, page: "Page", expect: dict) -> list[AssertionResult]:
        """Verify a single expectation dict (may contain multiple assertions)."""
        results = []

        # URL assertions
        if "url" in expect:
            results.append(await self.url(page, expect["url"]))

        if "url_contains" in expect:
            results.append(await self.url_contains(page, expect["url_contains"]))

        if "url_matches" in expect:
            results.append(await self.url_matches(page, expect["url_matches"]))

        # Element assertions
        if "visible" in expect:
            results.append(await self.visible(page, expect["visible"]))

        if "hidden" in expect:
            results.append(await self.hidden(page, expect["hidden"]))

        if "exists" in expect:
            results.append(await self.exists(page, expect["exists"]))

        # Text assertions
        if "text_contains" in expect:
            selector = expect.get("selector")
            results.append(await self.text_contains(page, expect["text_contains"], selector))

        if "text" in expect:
            text_data = expect["text"]
            results.append(await self.text_equals(page, text_data["selector"], text_data["value"]))

        # Value assertions
        if "value" in expect:
            value_data = expect["value"]
            results.append(await self.value(page, value_data["selector"], value_data["value"]))

        # Count assertions
        if "count" in expect:
            count_data = expect["count"]
            results.append(await self.count(page, count_data["selector"], count_data["value"]))

        return results

    async def url(self, page: "Page", expected: str) -> AssertionResult:
        """Assert URL matches exactly.

        Args:
            page: Playwright page
            expected: Expected URL or path
        """
        try:
            current_url = page.url
            # Normalize for path comparison
            if expected.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                actual = parsed.path
                passed = actual == expected or actual.rstrip("/") == expected.rstrip("/")
            else:
                actual = current_url
                passed = actual == expected

            return AssertionResult(
                type="url",
                expected=expected,
                actual=actual,
                passed=passed,
                message=f"URL {'matches' if passed else 'does not match'}",
            )

        except Exception as e:
            logger.error(f"URL assertion failed: {e}")
            return AssertionResult(
                type="url",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def url_contains(self, page: "Page", expected: str) -> AssertionResult:
        """Assert URL contains substring.

        Args:
            page: Playwright page
            expected: Expected substring
        """
        try:
            current_url = page.url
            passed = expected in current_url

            return AssertionResult(
                type="url_contains",
                expected=expected,
                actual=current_url,
                passed=passed,
                message=f"URL {'contains' if passed else 'does not contain'} '{expected}'",
            )

        except Exception as e:
            logger.error(f"URL contains assertion failed: {e}")
            return AssertionResult(
                type="url_contains",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def url_matches(self, page: "Page", pattern: str) -> AssertionResult:
        """Assert URL matches regex pattern.

        Args:
            page: Playwright page
            pattern: Regex pattern to match
        """
        import re

        try:
            current_url = page.url
            passed = bool(re.search(pattern, current_url))

            return AssertionResult(
                type="url_matches",
                expected=pattern,
                actual=current_url,
                passed=passed,
                message=f"URL {'matches' if passed else 'does not match'} pattern '{pattern}'",
            )

        except Exception as e:
            logger.error(f"URL matches assertion failed: {e}")
            return AssertionResult(
                type="url_matches",
                expected=pattern,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def visible(self, page: "Page", selector: str) -> AssertionResult:
        """Assert element is visible.

        Args:
            page: Playwright page
            selector: CSS selector
        """
        try:
            # Handle multiple selectors (comma-separated)
            selectors = [s.strip() for s in selector.split(",")]
            visible = False
            found_selector = None

            for sel in selectors:
                try:
                    element = await page.wait_for_selector(sel, timeout=3000, state="visible")
                    if element:
                        visible = True
                        found_selector = sel
                        break
                except Exception:
                    continue

            return AssertionResult(
                type="visible",
                expected=selector,
                actual=found_selector if visible else "Not found",
                passed=visible,
                message=f"Element {'is' if visible else 'is not'} visible",
            )

        except Exception as e:
            logger.error(f"Visible assertion failed: {e}")
            return AssertionResult(
                type="visible",
                expected=selector,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def hidden(self, page: "Page", selector: str) -> AssertionResult:
        """Assert element is hidden or not present.

        Args:
            page: Playwright page
            selector: CSS selector
        """
        try:
            element = await page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                hidden = not is_visible
            else:
                hidden = True  # Not present = hidden

            return AssertionResult(
                type="hidden",
                expected=selector,
                actual="hidden" if hidden else "visible",
                passed=hidden,
                message=f"Element {'is' if hidden else 'is not'} hidden",
            )

        except Exception as e:
            logger.error(f"Hidden assertion failed: {e}")
            return AssertionResult(
                type="hidden",
                expected=selector,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def exists(self, page: "Page", selector: str) -> AssertionResult:
        """Assert element exists in DOM.

        Args:
            page: Playwright page
            selector: CSS selector
        """
        try:
            element = await page.query_selector(selector)
            exists = element is not None

            return AssertionResult(
                type="exists",
                expected=selector,
                actual="exists" if exists else "not found",
                passed=exists,
                message=f"Element {'exists' if exists else 'does not exist'}",
            )

        except Exception as e:
            logger.error(f"Exists assertion failed: {e}")
            return AssertionResult(
                type="exists",
                expected=selector,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def text_contains(
        self, page: "Page", expected: str, selector: Optional[str] = None
    ) -> AssertionResult:
        """Assert page or element contains text.

        Args:
            page: Playwright page
            expected: Expected text substring
            selector: Optional CSS selector (defaults to body)
        """
        try:
            if selector:
                element = await page.query_selector(selector)
                if element:
                    actual = await element.text_content() or ""
                else:
                    return AssertionResult(
                        type="text_contains",
                        expected=expected,
                        actual=f"Element not found: {selector}",
                        passed=False,
                        message=f"Element {selector} not found",
                    )
            else:
                actual = await page.text_content("body") or ""

            passed = expected in actual

            return AssertionResult(
                type="text_contains",
                expected=expected,
                actual=actual[:100] + "..." if len(actual) > 100 else actual,
                passed=passed,
                message=f"Text {'contains' if passed else 'does not contain'} '{expected}'",
            )

        except Exception as e:
            logger.error(f"Text contains assertion failed: {e}")
            return AssertionResult(
                type="text_contains",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def text_equals(self, page: "Page", selector: str, expected: str) -> AssertionResult:
        """Assert element text equals expected.

        Args:
            page: Playwright page
            selector: CSS selector
            expected: Expected exact text
        """
        try:
            element = await page.query_selector(selector)
            if element:
                actual = (await element.text_content() or "").strip()
            else:
                return AssertionResult(
                    type="text",
                    expected=expected,
                    actual=f"Element not found: {selector}",
                    passed=False,
                    message=f"Element {selector} not found",
                )

            passed = actual == expected

            return AssertionResult(
                type="text",
                expected=expected,
                actual=actual,
                passed=passed,
                message=f"Text {'matches' if passed else 'does not match'}",
            )

        except Exception as e:
            logger.error(f"Text equals assertion failed: {e}")
            return AssertionResult(
                type="text",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def value(self, page: "Page", selector: str, expected: str) -> AssertionResult:
        """Assert input value equals expected.

        Args:
            page: Playwright page
            selector: CSS selector
            expected: Expected value
        """
        try:
            actual = await page.input_value(selector)
            passed = actual == expected

            return AssertionResult(
                type="value",
                expected=expected,
                actual=actual,
                passed=passed,
                message=f"Value {'matches' if passed else 'does not match'}",
            )

        except Exception as e:
            logger.error(f"Value assertion failed: {e}")
            return AssertionResult(
                type="value",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )

    async def count(self, page: "Page", selector: str, expected: int) -> AssertionResult:
        """Assert element count.

        Args:
            page: Playwright page
            selector: CSS selector
            expected: Expected count
        """
        try:
            elements = await page.query_selector_all(selector)
            actual = len(elements)
            passed = actual == expected

            return AssertionResult(
                type="count",
                expected=expected,
                actual=actual,
                passed=passed,
                message=f"Count {'matches' if passed else 'does not match'} ({actual} elements)",
            )

        except Exception as e:
            logger.error(f"Count assertion failed: {e}")
            return AssertionResult(
                type="count",
                expected=expected,
                actual=str(e),
                passed=False,
                message=f"Error: {e}",
            )
