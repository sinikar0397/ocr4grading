import shutil
import subprocess
import tempfile
from pathlib import Path

MINERU_BIN = shutil.which("mineru") or "mineru"


def run_mineru(input_path: str) -> str:
    """Run the MinerU CLI on a PDF or image and return its extracted markdown text."""
    with tempfile.TemporaryDirectory() as out_dir:
        result = subprocess.run(
            [MINERU_BIN, "-p", input_path, "-o", out_dir, "-b", "pipeline", "-l", "korean"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"mineru failed: {result.stderr[-2000:]}")

        md_files = sorted(Path(out_dir).rglob("*.md"))
        if not md_files:
            raise RuntimeError("mineru produced no markdown output")
        return "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)
