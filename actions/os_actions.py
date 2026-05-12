"""OS-level actions: open apps, focus windows. Platform-aware."""

import sys
import asyncio
from loguru import logger


async def open_app(app_name: str) -> dict:
    """Open an application by name. Platform-aware."""
    try:
        if sys.platform == "darwin":
            proc = await asyncio.create_subprocess_exec(
                "open", "-a", app_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip())

        elif sys.platform == "win32":
            proc = await asyncio.create_subprocess_shell(
                f'start "" "{app_name}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        else:
            raise RuntimeError(f"open_app not supported on {sys.platform}")

        logger.info(f"Opened app: {app_name}")
        return {"status": "ok", "result": f"Opened {app_name}"}

    except Exception as e:
        logger.error(f"open_app failed for '{app_name}': {e}")
        return {"status": "error", "result": str(e)}


async def focus_window(window_title: str) -> dict:
    """Bring a window to the foreground. Platform-aware."""
    try:
        if sys.platform == "darwin":
            script = f'tell application "{window_title}" to activate'
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip())

        elif sys.platform == "win32":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _focus_window_win32, window_title)

        else:
            raise RuntimeError(f"focus_window not supported on {sys.platform}")

        logger.info(f"Focused window: {window_title}")
        return {"status": "ok", "result": f"Focused {window_title}"}

    except Exception as e:
        logger.error(f"focus_window failed for '{window_title}': {e}")
        return {"status": "error", "result": str(e)}


def _focus_window_win32(window_title: str) -> None:
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle(window_title)
    if wins:
        wins[0].activate()
    else:
        raise RuntimeError(f"Window not found: {window_title}")
