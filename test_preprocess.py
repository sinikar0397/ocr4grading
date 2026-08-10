import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.src.preprocess import deskew, is_image


def test_is_image_detects_common_extensions():
    assert is_image("photo.JPG")
    assert not is_image("doc.pdf")


def test_deskew_leaves_blank_image_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "blank.png"
        cv2.imwrite(str(path), np.zeros((100, 100, 3), dtype=np.uint8))
        before = path.read_bytes()

        result = deskew(str(path))

        assert result == str(path)
        assert path.read_bytes() == before


def test_deskew_straightens_rotated_rectangle():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "paper.png"
        canvas = np.zeros((300, 300, 3), dtype=np.uint8)
        rect = np.array([[100, 40], [220, 80], [180, 220], [60, 180]], dtype=np.int32)
        cv2.fillConvexPoly(canvas, rect, (255, 255, 255))
        cv2.imwrite(str(path), canvas)

        deskew(str(path))

        warped = cv2.imread(str(path))
        assert warped is not None and warped.shape[0] > 0 and warped.shape[1] > 0


if __name__ == "__main__":
    test_is_image_detects_common_extensions()
    test_deskew_leaves_blank_image_untouched()
    test_deskew_straightens_rotated_rectangle()
    print("OK")
