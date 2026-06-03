"""Focused tests for hardened shell and file safety guards."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

if "loguru" not in sys.modules:
    sys.modules["loguru"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None)
    )

if "aiofiles" not in sys.modules:
    class _AsyncFileWrapper:
        def __init__(self, path: str | Path, mode: str):
            self._path = Path(path)
            self._mode = mode
            self._handle = None

        async def __aenter__(self):
            self._handle = self._path.open(self._mode, encoding="utf-8")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            if self._handle is not None:
                self._handle.close()
            return False

        async def read(self):
            return self._handle.read()

        async def write(self, content: str):
            self._handle.write(content)

    sys.modules["aiofiles"] = types.SimpleNamespace(open=lambda path, mode="r": _AsyncFileWrapper(path, mode))

from actions.file_actions import delete_file, move_file, write_file
from actions.shell_actions import run_shell


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_shell_blocks_chaining_and_redirection(self) -> None:
        result = await run_shell("echo hello && dir")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("redirection", result["result"].lower())

    async def test_run_shell_blocks_unknown_command(self) -> None:
        result = await run_shell("curl https://example.com")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("allowlist", result["result"].lower())

    async def test_run_shell_allows_simple_safe_command(self) -> None:
        result = await run_shell("py --version")
        self.assertEqual(result["status"], "ok")
        self.assertIn("python", result["result"].lower())

    async def test_write_file_blocks_protected_root_path(self) -> None:
        result = await write_file(str(Path.home()), "nope")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("protected path", result["result"].lower())

    async def test_delete_file_blocks_home_directory(self) -> None:
        result = await delete_file(str(Path.home()))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("protected path", result["result"].lower())

    async def test_move_file_blocks_protected_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "note.txt"
            src.write_text("hello", encoding="utf-8")
            protected_base = Path.home()
            if "SystemRoot" in __import__("os").environ:
                protected_base = Path(__import__("os").environ["SystemRoot"])
            result = await move_file(str(src), str(protected_base / "moved.txt"))
            self.assertEqual(result["status"], "blocked")
            self.assertIn("protected path", result["result"].lower())

    async def test_write_file_allows_temp_workspace_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "safe.txt"
            result = await write_file(str(target), "hello")
            self.assertEqual(result["status"], "ok")
            self.assertTrue(target.exists())
