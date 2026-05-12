"""Clipboard read/write via pyperclip."""

import asyncio
import pyperclip
from loguru import logger


async def get_clipboard() -> dict:
    """Read the current clipboard contents."""
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, pyperclip.paste)
        logger.debug(f"Clipboard read: {len(text)} chars")
        return {"status": "ok", "result": text}
    except Exception as e:
        logger.error(f"get_clipboard error: {e}")
        return {"status": "error", "result": str(e)}


async def set_clipboard(text: str) -> dict:
    """Write text to the clipboard."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, pyperclip.copy, text)
        logger.info(f"Clipboard set: {len(text)} chars")
        return {"status": "ok", "result": "Clipboard updated"}
    except Exception as e:
        logger.error(f"set_clipboard error: {e}")
        return {"status": "error", "result": str(e)}
