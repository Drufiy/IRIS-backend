"""Tests for Aryan's browser modules."""

from __future__ import annotations

import unittest

from browser.browser_agent import BrowserAgent
from browser.scraper import ContentScraper


class FakeLocator:
    async def inner_text(self) -> str:
        return "Hello   world"


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions: list[tuple[str, str, str | None]] = []

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.url = url
        self.actions.append(("goto", url, wait_until))

    async def click(self, selector: str) -> None:
        self.actions.append(("click", selector, None))

    async def fill(self, selector: str, text: str) -> None:
        self.actions.append(("fill", selector, text))

    async def query_selector(self, selector: str):
        self.actions.append(("query", selector, None))
        return FakeLocator()

    async def screenshot(self, full_page: bool = True) -> bytes:
        self.actions.append(("screenshot", str(full_page), None))
        return b"image"

    async def evaluate(self, script: str):
        self.actions.append(("evaluate", script, None))
        return {"ok": True}


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_agent_routes_actions_to_page(self) -> None:
        page = FakePage()
        agent = BrowserAgent(page=page)
        url = await agent.navigate("https://example.com")
        text = await agent.extract_text()
        screenshot = await agent.screenshot()
        result = await agent.run_js("() => true")
        self.assertEqual(url, "https://example.com")
        self.assertEqual(text, "Hello   world")
        self.assertEqual(screenshot, b"image")
        self.assertEqual(result, {"ok": True})

    async def test_scraper_cleans_text(self) -> None:
        scraper = ContentScraper()
        cleaned = scraper.clean_text("<p>Hello</p>\n<p>world</p>")
        self.assertEqual(cleaned, "Hello world")
