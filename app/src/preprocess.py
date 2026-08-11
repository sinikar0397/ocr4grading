from pathlib import Path

import cv2
import numpy as np

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def _order_corners(points: np.ndarray) -> np.ndarray:
    s = points.sum(axis=1)
    diff = np.diff(points, axis=1).flatten()
    top_left = points[np.argmin(s)]
    bottom_right = points[np.argmax(s)]
    top_right = points[np.argmin(diff)]
    bottom_left = points[np.argmax(diff)]
    return np.array([top_left, top_right, bottom_right, bottom_left], dtype="float32")


def deskew(path: str) -> str:
    """Best-effort perspective correction for a photographed exam page.

    Overwrites the file in place and returns the same path. Leaves the image
    untouched whenever a clean page contour can't be found, rather than
    failing the request over a bad crop.
    """
    image = cv2.imread(path)
    if image is None:
        return path

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(blurred, 50, 150), None, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return path

    largest = max(contours, key=cv2.contourArea)
    image_area = image.shape[0] * image.shape[1]
    # ponytail: contour-based deskew, fails on low-contrast backgrounds or
    # cluttered desks; add a manual 4-point picker in the UI if that happens often.
    if cv2.contourArea(largest) < image_area * 0.2:
        return path

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return path

    corners = _order_corners(approx.reshape(4, 2).astype("float32"))
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
    height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
    if width <= 0 or height <= 0:
        return path

    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(corners, dst)
    warped = cv2.warpPerspective(image, matrix, (width, height))
    cv2.imwrite(path, warped)
    return path
