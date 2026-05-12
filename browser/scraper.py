"""Content extraction helpers for browser automation."""

from __future__ import annotations

import re
from html import unescape


class ContentScraper:
    """Extracts readable text from raw HTML or a browser page."""

    async def from_page(self, browser, selector: str = "body") -> str:
        """Returns cleaned text extracted from a live browser page."""
        text = await browser.extract_text(selector)
        return self.clean_text(text)

    def clean_text(self, value: str) -> str:
        """Normalizes whitespace and strips raw HTML tags if present."""
        text = re.sub(r"<[^>]+>", " ", value)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
