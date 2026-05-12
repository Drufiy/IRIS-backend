"""File system actions — read / write / move / delete."""

import asyncio
import shutil
from pathlib import Path
from loguru import logger
import aiofiles


async def read_file(file_path: str) -> dict:
    """Read and return file contents."""
    p = Path(file_path).expanduser()
    if not p.exists():
        return {"status": "error", "result": f"File not found: {file_path}"}
    try:
        async with aiofiles.open(p, mode="r") as f:
            content = await f.read()
        logger.debug(f"Read file: {p} ({len(content)} chars)")
        return {"status": "ok", "result": content}
    except Exception as e:
        logger.error(f"read_file error: {e}")
        return {"status": "error", "result": str(e)}


async def write_file(file_path: str, content: str) -> dict:
    """Write content to a file, creating parent dirs as needed."""
    p = Path(file_path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(p, mode="w") as f:
            await f.write(content)
        logger.info(f"Wrote file: {p} ({len(content)} chars)")
        return {"status": "ok", "result": f"Written to {p}"}
    except Exception as e:
        logger.error(f"write_file error: {e}")
        return {"status": "error", "result": str(e)}


async def move_file(src: str, dst: str) -> dict:
    """Move/rename a file."""
    src_p = Path(src).expanduser()
    dst_p = Path(dst).expanduser()
    if not src_p.exists():
        return {"status": "error", "result": f"Source not found: {src}"}
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.move, str(src_p), str(dst_p))
        logger.info(f"Moved: {src_p} → {dst_p}")
        return {"status": "ok", "result": f"Moved to {dst_p}"}
    except Exception as e:
        logger.error(f"move_file error: {e}")
        return {"status": "error", "result": str(e)}


async def delete_file(file_path: str) -> dict:
    """Delete a file. DANGEROUS — requires approval."""
    p = Path(file_path).expanduser()
    if not p.exists():
        return {"status": "error", "result": f"File not found: {file_path}"}
    try:
        loop = asyncio.get_event_loop()
        if p.is_dir():
            await loop.run_in_executor(None, shutil.rmtree, str(p))
        else:
            await loop.run_in_executor(None, p.unlink)
        logger.info(f"Deleted: {p}")
        return {"status": "ok", "result": f"Deleted {p}"}
    except Exception as e:
        logger.error(f"delete_file error: {e}")
        return {"status": "error", "result": str(e)}
