"""Structured logging for IRIS via loguru."""

import sys
from loguru import logger


def setup_logger(log_level: str = "DEBUG", log_file: str = "logs/iris.log") -> logger:
    """Configure loguru with console + rotating file sinks."""
    logger.remove()

    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
        colorize=True,
    )

    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        enqueue=True,
    )

    return logger
