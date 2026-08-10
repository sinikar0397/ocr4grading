import shutil
import uuid
from pathlib import Path

DATA_DIR = Path("data")
PENDING_DIR = DATA_DIR / "_pending"
EXAMS_DIR = DATA_DIR / "exams"


def pending_dir(preview_id: str) -> Path:
    return PENDING_DIR / preview_id


def new_preview_id() -> str:
    return uuid.uuid4().hex


def save_upload(preview_id: str, field: str, filename: str, content: bytes) -> Path:
    """Save an uploaded file's bytes under data/_pending/<preview_id>/<field>.<ext>."""
    directory = pending_dir(preview_id)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "").suffix
    dest = directory / f"{field}{suffix}"
    dest.write_bytes(content)
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
    src = pending_dir(preview_id)
    if not src.exists():
        raise FileNotFoundError(f"no pending upload for preview_id={preview_id}")

    dest = EXAMS_DIR / str(exam_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return resolved_paths(dest)
