"""Tests for Aryan's browser modules."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from browser.browser_agent import BrowserAgent
from browser.login_handler import LoginHandler
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

    async def test_login_handler_encrypts_and_loads_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            credentials_path = Path(tmp) / "credentials.json"
            handler = LoginHandler(str(credentials_path), secret="super-secret")

            await handler.save_credentials(
                "github",
                {"username": "aryan", "password": "token-123"},
            )

            raw = json.loads(credentials_path.read_text(encoding="utf-8"))
            self.assertIn("services", raw)
            self.assertNotIn("username", credentials_path.read_text(encoding="utf-8"))

            loaded = await handler.load_credentials("github")
            self.assertEqual(loaded["username"], "aryan")
            self.assertEqual(loaded["password"], "token-123")

    async def test_login_handler_applies_credentials_to_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            credentials_path = Path(tmp) / "credentials.json"
            handler = LoginHandler(str(credentials_path), secret="super-secret")
            await handler.save_credentials(
                "github",
                {"username": "aryan", "password": "token-123"},
            )

            page = FakePage()
            agent = BrowserAgent(page=page)
            await handler.login(agent, "github", "#user", "#pass", "#submit")

            self.assertIn(("fill", "#user", "aryan"), page.actions)
            self.assertIn(("fill", "#pass", "token-123"), page.actions)
            self.assertIn(("click", "#submit", None), page.actions)
