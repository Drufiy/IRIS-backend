"""Background process entrypoint for IRIS daemon mode."""

import asyncio
import signal
import sys
from loguru import logger


async def _shutdown(loop: asyncio.AbstractEventLoop, sig: signal.Signals) -> None:
    """Graceful shutdown on SIGINT / SIGTERM."""
    logger.info(f"Received {sig.name}, shutting down IRIS...")
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()
    logger.info("IRIS daemon stopped")


def run_daemon() -> None:
    """
    Entry point for running IRIS as a background daemon.
    Imports main() from main.py and attaches signal handlers.
    """
    from main import main

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(_shutdown(loop, s))
        )

    try:
        logger.info("Starting IRIS daemon...")
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.close()
        logger.info("Event loop closed")


if __name__ == "__main__":
    run_daemon()
