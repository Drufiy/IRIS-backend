"""Screenshot (mss) + OCR (easyocr) actions."""

import asyncio
from pathlib import Path
from loguru import logger


async def take_screenshot(output_path: str = None) -> dict:
    """Capture the primary monitor. Returns the file path or raw bytes."""
    try:
        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(None, _screenshot_sync, output_path)
        logger.info(f"Screenshot saved: {path}")
        return {"status": "ok", "result": str(path)}
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {"status": "error", "result": str(e)}


def _screenshot_sync(output_path: str = None) -> Path:
    import mss
    save_path = Path(output_path) if output_path else Path("screenshots/screen.png")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(save_path))
    return save_path


async def ocr_screenshot(image_path: str) -> dict:
    """Run OCR on an image and return extracted text."""
    p = Path(image_path)
    if not p.exists():
        return {"status": "error", "result": f"Image not found: {image_path}"}

    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _ocr_sync, str(p))
        logger.info(f"OCR extracted {len(text)} chars from {p}")
        return {"status": "ok", "result": text}
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return {"status": "error", "result": str(e)}


def _ocr_sync(image_path: str) -> str:
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(image_path)
    return "\n".join(text for _, text, _ in results)
