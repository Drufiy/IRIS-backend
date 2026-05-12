"""Async browser automation wrapper."""

from __future__ import annotations


class BrowserUnavailableError(RuntimeError):
    """Raised when Playwright is unavailable in the local environment."""


class BrowserAgent:
    """Thin async abstraction over a single browser page."""

    def __init__(self, page=None):
        self._playwright = None
        self._browser = None
        self._page = page

    async def start(self, headless: bool = False) -> None:
        """Launches a browser and creates a page when Playwright is available."""
        if self._page is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailableError("Playwright is not installed.") from exc

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)
        self._page = await self._browser.new_page()

    async def navigate(self, url: str) -> str:
        """Navigates to a URL and returns the final page URL."""
        self._require_page()
        await self._page.goto(url, wait_until="domcontentloaded")
        return self._page.url

    async def click(self, selector: str) -> None:
        """Clicks an element on the page."""
        self._require_page()
        await self._page.click(selector)

    async def type_text(self, selector: str, text: str) -> None:
        """Types text into an element on the page."""
        self._require_page()
        await self._page.fill(selector, text)

    async def extract_text(self, selector: str = "body") -> str:
        """Extracts visible text from the selected element."""
        self._require_page()
        locator = await self._page.query_selector(selector)
        return await locator.inner_text() if locator else ""

    async def screenshot(self) -> bytes:
        """Captures a full-page screenshot."""
        self._require_page()
        return await self._page.screenshot(full_page=True)

    async def run_js(self, script: str):
        """Evaluates JavaScript in the current page."""
        self._require_page()
        return await self._page.evaluate(script)

    async def close(self) -> None:
        """Closes browser resources."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    def _require_page(self) -> None:
        if self._page is None:
            raise BrowserUnavailableError("Browser page has not been started.")
