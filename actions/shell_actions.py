"""Shell command execution — safe + guarded."""

import asyncio
import shlex
from loguru import logger

BLOCKED_COMMANDS = {"rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:"}
SUDO_PREFIX = "sudo "


def is_sudo(command: str) -> bool:
    """Check if a command requires sudo."""
    return command.strip().startswith(SUDO_PREFIX)


def _is_blocked(command: str) -> bool:
    """Reject obviously destructive commands."""
    normalized = command.strip().lower()
    return any(blocked in normalized for blocked in BLOCKED_COMMANDS)


async def run_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command and return stdout/stderr."""
    if _is_blocked(command):
        logger.warning(f"Blocked dangerous command: {command}")
        return {"status": "blocked", "result": "Command blocked by safety filter"}

    logger.info(f"Shell exec: {command}")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode().strip()
        errors = stderr.decode().strip()

        if proc.returncode == 0:
            logger.debug(f"Shell OK (rc=0): {output[:200]}")
            return {"status": "ok", "result": output or "(no output)"}
        else:
            logger.warning(f"Shell failed (rc={proc.returncode}): {errors}")
            return {"status": "error", "result": errors or output, "returncode": proc.returncode}

    except asyncio.TimeoutError:
        logger.error(f"Shell command timed out ({timeout}s): {command}")
        proc.kill()
        return {"status": "error", "result": f"Timed out after {timeout}s"}
    except Exception as e:
        logger.error(f"Shell exec error: {e}")
        return {"status": "error", "result": str(e)}
