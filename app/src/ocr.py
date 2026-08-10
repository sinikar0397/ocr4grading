import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .preprocess import deskew, is_image

MINERU_BIN = shutil.which("mineru") or "mineru"

# Model weights are already downloaded (see `mineru-models-download`) and
# registered in ~/mineru.json's "models-dir". Force local-only resolution so
# mineru never re-checks huggingface/modelscope for updates at run time.
MINERU_ENV = {
    **os.environ,
    "MINERU_MODEL_SOURCE": "local",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}


def run_mineru(input_path: str) -> str:
    """Run the MinerU CLI on a PDF or image and return its extracted markdown text."""
    if is_image(input_path):
        input_path = deskew(input_path)

    with tempfile.TemporaryDirectory() as out_dir:
        result = subprocess.run(
            [MINERU_BIN, "-p", input_path, "-o", out_dir, "-b", "pipeline", "-l", "korean"],
            capture_output=True,
            text=True,
            env=MINERU_ENV,
        )
        if result.returncode != 0:
            raise RuntimeError(f"mineru failed: {result.stderr[-2000:]}")

        md_files = sorted(Path(out_dir).rglob("*.md"))
        if not md_files:
            raise RuntimeError("mineru produced no markdown output")
        return "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)
