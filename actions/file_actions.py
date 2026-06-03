"""File system actions — read / write / move / delete."""

import asyncio
import os
import shutil
from pathlib import Path
from loguru import logger
import aiofiles


PROTECTED_PATH_PREFIXES = {
    Path("/"),
    Path.home(),
}
for env_name in ("SystemRoot", "WINDIR", "ProgramFiles", "ProgramFiles(x86)"):
    value = os.getenv(env_name)
    if value:
        PROTECTED_PATH_PREFIXES.add(Path(value))


def _resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve(strict=False)


def _is_protected_path(path: Path) -> bool:
    """Reject writes/moves/deletes against highly sensitive locations."""
    if path == path.anchor:
        return True
    if len(path.parts) <= 1:
        return True
    for protected in PROTECTED_PATH_PREFIXES:
        try:
            if protected == Path.home():
                if path == protected:
                    return True
                continue
            if path == protected or protected in path.parents:
                return True
        except Exception:
            continue
    return False


def _guard_path(path_str: str) -> tuple[bool, str, Path]:
    path = _resolve_path(path_str)
    if _is_protected_path(path):
        return False, f"Refusing to operate on protected path: {path}", path
    return True, "", path


async def read_file(file_path: str) -> dict:
    """Read and return file contents."""
    p = _resolve_path(file_path)
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
    ok, message, p = _guard_path(file_path)
    if not ok:
        logger.warning(message)
        return {"status": "blocked", "result": message}
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
    src_ok, src_message, src_p = _guard_path(src)
    if not src_ok:
        logger.warning(src_message)
        return {"status": "blocked", "result": src_message}
    dst_ok, dst_message, dst_p = _guard_path(dst)
    if not dst_ok:
        logger.warning(dst_message)
        return {"status": "blocked", "result": dst_message}
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
    ok, message, p = _guard_path(file_path)
    if not ok:
        logger.warning(message)
        return {"status": "blocked", "result": message}
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
