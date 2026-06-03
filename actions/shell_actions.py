"""Shell command execution — safe + guarded."""

import asyncio
import os
import shlex
from loguru import logger

BLOCKED_COMMANDS = {"rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:"}
BLOCKED_TOKENS = {"rm", "mkfs", "dd", "shutdown", "reboot", "format", "del", "rd", "rmdir"}
BLOCKED_METACHARS = {"|", "&&", "||", ";", ">", ">>", "<", "$(", "`"}
ALLOWED_COMMANDS = {
    "pwd",
    "cd",
    "dir",
    "ls",
    "echo",
    "type",
    "cat",
    "rg",
    "git",
    "python",
    "py",
    "pip",
    "npm",
    "node",
    "cargo",
}
SUDO_PREFIX = "sudo "


def is_sudo(command: str) -> bool:
    """Check if a command requires sudo."""
    return command.strip().startswith(SUDO_PREFIX)


def _is_blocked(command: str) -> bool:
    """Reject obviously destructive commands."""
    normalized = command.strip().lower()
    if any(blocked in normalized for blocked in BLOCKED_COMMANDS):
        return True
    if any(token in normalized for token in BLOCKED_METACHARS):
        return True
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return True
    if not parts:
        return True
    command_name = parts[0].lower()
    if command_name == "sudo":
        return True
    if command_name in BLOCKED_TOKENS:
        return True
    if command_name not in ALLOWED_COMMANDS:
        return True
    if any(part in {"/", "~", "%userprofile%", "c:\\", "c:/"} for part in (item.lower() for item in parts[1:])):
        return True
    return False


def _blocked_reason(command: str) -> str:
    """Explain why a shell command was rejected."""
    normalized = command.strip().lower()
    if any(blocked in normalized for blocked in BLOCKED_COMMANDS):
        return "Command matches a destructive blocklist entry."
    if any(token in normalized for token in BLOCKED_METACHARS):
        return "Shell chaining/redirection is not allowed."
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return "Command could not be parsed safely."
    if not parts:
        return "Empty commands are not allowed."
    command_name = parts[0].lower()
    if command_name == "sudo":
        return "sudo commands must go through the dangerous-action path."
    if command_name in BLOCKED_TOKENS:
        return f"The command '{command_name}' is blocked."
    if command_name not in ALLOWED_COMMANDS:
        return f"The command '{command_name}' is not in the safe allowlist."
    return "Command failed safety validation."


async def run_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command and return stdout/stderr."""
    if _is_blocked(command):
        logger.warning(f"Blocked dangerous command: {command}")
        return {"status": "blocked", "result": _blocked_reason(command)}

    logger.info(f"Shell exec: {command}")
    try:
        parts = shlex.split(command, posix=os.name != "nt")
        if not parts:
            return {"status": "blocked", "result": "Empty commands are not allowed."}
        proc = await asyncio.create_subprocess_exec(
            *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode().strip()
        errors = stderr.decode().strip()

        if proc.returncode == 0:
            result_text = output or errors or "(no output)"
            logger.debug(f"Shell OK (rc=0): {result_text[:200]}")
            return {"status": "ok", "result": result_text}
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
