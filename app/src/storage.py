import shutil
import os
import uuid
from pathlib import Path
from pypdfium2 import PdfPage
from PIL import Image

DATA_DIR = Path("data")
PENDING_DIR = DATA_DIR / "_pending"
EXAMS_DIR = DATA_DIR / "exams"

def pending_exam_dir(preview_id: str) -> Path:
    return PENDING_DIR / preview_id

def exam_dir(exam_id: int) -> Path:
    return EXAMS_DIR / str(exam_id)

def pending_page_dir(preview_id: str) -> Path:
    return pending_exam_dir(preview_id) /  "pages"

def pending_question_dir(preview_id: str) -> Path:
    return pending_exam_dir(preview_id) / "question"

def new_preview_id() -> str:
    return uuid.uuid4().hex

def save_upload(directory: Path, filename: str, content: bytes) -> Path:
    """save uploaded file's bytes and return it's path"""
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / filename
    dest.write_bytes(content)
    return dest

def save_upload_pending_exam(preview_id: str, field: str, filename: str, content: bytes) -> Path:
    """Save an uploaded file's bytes under data/_pending/<preview_id>/<field>.<ext>."""
    directory = pending_exam_dir(preview_id)
    suffix = Path(filename or "").suffix
    return save_upload(directory, f"{field}{suffix}", content)

def save_upload_pending_page(preview_id: str, field: str, index: int, page: PdfPage) -> Path:
    """Save an uploaded file(probably image)'s bytes under data/_pending/<preview_id>/pages/<filed>_<index>.png."""
    directory = pending_page_dir(preview_id)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{field}_{index}.png"
    page.render(scale=2).to_pil().save(dest)
    return dest

def read_pending_page(preview_id: str, field: str, index: int) -> Image:
    """read data/_pending/<preview_id>/pages/<filed>_page_<index>.png"""
    directory = pending_page_dir(preview_id)
    page_path = directory / f"{field}_{index}.png"
    return Image.open(page_path)

def save_upload_pending_question(preview_id : str, field: str, index: int, image: Image) -> Path:
    """Save an uploaded Image under data/_pending/<preview_id>/questions/<filed>_<index>.png.

    If this question already has a crop (e.g. the prompt and the question body
    were cropped separately), stack the new one below it instead of overwriting.
    """
    directory = pending_question_dir(preview_id)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{field}_{index}.png"
    if dest.exists():
        existing = Image.open(dest)
        width = max(existing.width, image.width)
        stacked = Image.new("RGB", (width, existing.height + image.height), "white")
        stacked.paste(existing, (0, 0))
        stacked.paste(image, (0, existing.height))
        image = stacked
    image.save(dest)
    return dest

def resolved_paths(directory: Path) -> dict[str, str]:
    paths = {}
    for field in ("exam", "answer"):
        matches = list(directory.glob(f"{field}.*"))
        if matches:
            paths[field] = str(matches[0])
    return paths

def promote_to_exam(preview_id: str, exam_id: int) -> dict[str, str]:
    """Move a pending upload directory into permanent storage for a confirmed exam."""
    src = pending_exam_dir(preview_id)
    if not src.exists():
        raise FileNotFoundError(f"no pending upload for preview_id={preview_id}")

    EXAMS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(EXAMS_DIR))
    dest = exam_dir(exam_id)
    os.rename(str(EXAMS_DIR / preview_id), str(dest))
    return resolved_paths(dest)
