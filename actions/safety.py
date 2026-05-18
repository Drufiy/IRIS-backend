"""Safety classifier — maps action types to SAFE / WARN / DANGEROUS."""

from enum import Enum
from loguru import logger


class SafetyLevel(Enum):
    SAFE      = "safe"       # Auto-execute silently
    WARN      = "warn"       # Execute + log with flag
    DANGEROUS = "dangerous"  # Require user approval popup


ACTION_SAFETY_MAP: dict[str, SafetyLevel] = {
    # SAFE
    "read_file":        SafetyLevel.SAFE,
    "open_app":         SafetyLevel.SAFE,
    "screenshot":       SafetyLevel.SAFE,
    "get_clipboard":    SafetyLevel.SAFE,
    "browser_navigate": SafetyLevel.SAFE,
    "browser_extract":  SafetyLevel.SAFE,

    # WARN
    "write_file":       SafetyLevel.WARN,
    "run_shell":        SafetyLevel.WARN,
    "set_clipboard":    SafetyLevel.WARN,
    "browser_click":    SafetyLevel.WARN,
    "browser_type":     SafetyLevel.WARN,
    "send_email":       SafetyLevel.WARN,
    "check_email":      SafetyLevel.SAFE,

    # DANGEROUS
    "delete_file":      SafetyLevel.DANGEROUS,
    "run_shell_sudo":   SafetyLevel.DANGEROUS,
    "browser_login":    SafetyLevel.DANGEROUS,
    "run_code":         SafetyLevel.DANGEROUS,
}


def classify(action_type: str) -> SafetyLevel:
    """Return safety level for action_type. Unknown actions default to DANGEROUS."""
    level = ACTION_SAFETY_MAP.get(action_type, SafetyLevel.DANGEROUS)
    if level == SafetyLevel.DANGEROUS and action_type not in ACTION_SAFETY_MAP:
        logger.warning(f"Unknown action type '{action_type}' — defaulting to DANGEROUS")
    return level
