"""Credential-backed browser login helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path


class LoginHandler:
    """Loads encrypted credentials and applies them to a browser page."""

    def __init__(self, credentials_path: str, secret: str | None = None):
        self.credentials_path = Path(credentials_path)
        self.secret = secret or os.environ.get("IRIS_CREDENTIAL_SECRET", "")

    async def save_credentials(self, service: str, credentials: dict[str, str]) -> None:
        """Encrypts and stores credentials for a named service."""
        payload = await self._read_payload()
        encrypted = self._encrypt(json.dumps(credentials))
        payload.setdefault("services", {})[service] = encrypted
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    async def load_credentials(self, service: str) -> dict[str, str]:
        """Loads credentials for a named service from local storage."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")

        payload = await self._read_payload()
        services = payload.get("services", {})
        if service not in services:
            raise KeyError(f"No credentials found for service '{service}'.")
        decrypted = self._decrypt(services[service])
        return json.loads(decrypted)

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

    async def _read_payload(self) -> dict:
        """Loads the credentials payload, supporting legacy plaintext storage."""
        if not self.credentials_path.exists():
            return {"version": 1, "encrypted": True, "services": {}}

        payload = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        if "services" in payload:
            return payload

        legacy_services: dict[str, str] = {}
        for service, credentials in payload.items():
            legacy_services[service] = self._encrypt(json.dumps(credentials))
        upgraded_payload = {"version": 1, "encrypted": True, "services": legacy_services}
        self.credentials_path.write_text(json.dumps(upgraded_payload, indent=2), encoding="utf-8")
        return upgraded_payload

    def _encrypt(self, plaintext: str) -> str:
        """Encrypts a credentials JSON string with a local secret."""
        key = self._key_stream()
        plaintext_bytes = plaintext.encode("utf-8")
        encrypted = bytes(
            byte ^ key[index % len(key)]
            for index, byte in enumerate(plaintext_bytes)
        )
        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypts a stored credentials JSON string."""
        key = self._key_stream()
        encrypted_bytes = base64.b64decode(ciphertext.encode("ascii"))
        plaintext = bytes(
            byte ^ key[index % len(key)]
            for index, byte in enumerate(encrypted_bytes)
        )
        return plaintext.decode("utf-8")

    def _key_stream(self) -> bytes:
        """Derives a deterministic local key stream from the configured secret."""
        if not self.secret:
            raise RuntimeError("No credential secret configured. Set IRIS_CREDENTIAL_SECRET before loading credentials.")
        return hashlib.sha256(self.secret.encode("utf-8")).digest()
