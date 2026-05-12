"""Credential-backed browser login helpers."""

from __future__ import annotations

import json
from pathlib import Path


class LoginHandler:
    """Loads stored credentials and applies them to a browser page."""

    def __init__(self, credentials_path: str):
        self.credentials_path = Path(credentials_path)

    async def load_credentials(self, service: str) -> dict[str, str]:
        """Loads credentials for a named service from local storage."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
        data = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        if service not in data:
            raise KeyError(f"No credentials found for service '{service}'.")
        return data[service]

    async def login(
        self,
        browser,
        service: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
    ) -> None:
        """Applies stored credentials to the current page."""
        credentials = await self.load_credentials(service)
        await browser.type_text(username_selector, credentials["username"])
        await browser.type_text(password_selector, credentials["password"])
        await browser.click(submit_selector)
