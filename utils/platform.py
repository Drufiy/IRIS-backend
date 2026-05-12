"""OS detection and platform-specific adapters."""

import sys
from loguru import logger


def get_platform() -> str:
    """Return 'macos', 'windows', or 'linux'."""
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform == "win32":
        return "windows"
    else:
        return "linux"


def open_application(app_name: str) -> bool:
    """Open an application by name. Platform-aware."""
    platform = get_platform()

    try:
        if platform == "macos":
            import subprocess
            subprocess.Popen(["open", "-a", app_name])
            logger.info(f"Opened app (macOS): {app_name}")
            return True

        elif platform == "windows":
            import subprocess
            subprocess.Popen(["start", app_name], shell=True)
            logger.info(f"Opened app (Windows): {app_name}")
            return True

        else:
            logger.warning(f"open_application not supported on {platform}")
            return False

    except Exception as e:
        logger.error(f"Failed to open {app_name}: {e}")
        return False


def focus_window(window_title: str) -> bool:
    """Bring a window to the foreground. Platform-aware."""
    platform = get_platform()

    try:
        if platform == "macos":
            import subprocess
            script = f'tell application "{window_title}" to activate'
            subprocess.run(["osascript", "-e", script], check=True)
            logger.info(f"Focused window (macOS): {window_title}")
            return True

        elif platform == "windows":
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(window_title)
            if wins:
                wins[0].activate()
                logger.info(f"Focused window (Windows): {window_title}")
                return True
            logger.warning(f"Window not found: {window_title}")
            return False

        else:
            logger.warning(f"focus_window not supported on {platform}")
            return False

    except Exception as e:
        logger.error(f"Failed to focus {window_title}: {e}")
        return False


def run_osascript(script: str) -> str:
    """Run an AppleScript command. macOS only."""
    if get_platform() != "macos":
        raise RuntimeError("osascript is macOS-only")
    import subprocess
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()
