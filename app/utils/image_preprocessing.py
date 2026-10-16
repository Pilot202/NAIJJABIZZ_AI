"""Image pre-processing for receipt OCR.

Phone photos of Nigerian shop receipts/invoices are often skewed, poorly lit,
noisy or low-contrast.  This module applies a deterministic pipeline that
significantly improves OCR accuracy before the text is sent to Tesseract or
EasyOCR.

Pipeline:  resize → grayscale → denoise → contrast (CLAHE) → deskew → binarize → border.
Each step can be toggled off via keyword arguments for experimentation.
"""
import io
import math
from typing import Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:  # opencv-python not installed
    cv2 = None  # type: ignore[assignment]

from PIL import Image


# ---------------------------------------------------------------------------
# Individual transforms
# ---------------------------------------------------------------------------

def _to_cv2(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes into a BGR OpenCV array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    return img


def resize(img: np.ndarray, max_dim: int = 2048) -> np.ndarray:
    """Down-scale very large images so OCR runs in reasonable time."""
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    scale = max_dim / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(img: np.ndarray, strength: int = 10) -> np.ndarray:
    """Non-local means denoising.  Works on grayscale or colour."""
    if len(img.shape) == 2:
        return cv2.fastNlMeansDenoising(img, None, strength)
    return cv2.fastNlMeansDenoisingColored(img, None, strength, strength)


def enhance_contrast(gray: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    """CLAHE (Contrast-Limited Adaptive Histogram Equalisation).

    Much better than global histogram equalisation for unevenly lit receipts.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return clahe.apply(gray)


def deskew(gray: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Correct small rotations via the Hough line transform.

    Only corrects up to ±max_angle degrees so a wildly rotated image is not
    made worse by a false detection.
    """
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=100,
                            minLineLength=gray.shape[1] // 4, maxLineGap=10)
    if lines is None:
        return gray
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) <= max_angle:
            angles.append(angle)
    if not angles:
        return gray
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.3:  # not worth rotating for <0.3°
        return gray
    h, w = gray.shape[:2]
    centre = (w // 2, h // 2)
    mat = cv2.getRotationMatrix2D(centre, median_angle, 1.0)
    return cv2.warpAffine(gray, mat, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def binarize(gray: np.ndarray, block_size: int = 31, c: int = 10) -> np.ndarray:
    """Adaptive thresholding.  Handles shadows and uneven illumination better
    than a global threshold (Otsu's).
    """
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, block_size, c)


def add_border(img: np.ndarray, px: int = 20) -> np.ndarray:
    """Add a white border so Tesseract does not clip characters at the edges."""
    return cv2.copyMakeBorder(img, px, px, px, px,
                              cv2.BORDER_CONSTANT, value=255 if len(img.shape) == 2 else (255, 255, 255))


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def preprocess_receipt(
    image_bytes: bytes,
    *,
    do_resize: bool = True,
    do_denoise: bool = True,
    do_contrast: bool = True,
    do_deskew: bool = True,
    do_binarize: bool = True,
    do_border: bool = True,
) -> Tuple[np.ndarray, Image.Image]:
    """Run the full pre-processing pipeline.

    Returns:
        (cv2_array, pil_image)  — the cv2 array for EasyOCR, the PIL image for
        Tesseract / general use.
    """
    if cv2 is None:
        # Fall back: return the image as-is (no preprocessing) when OpenCV is
        # not installed.  OCR will still work, just less accurately.
        pil = Image.open(io.BytesIO(image_bytes)).convert("L")
        return np.array(pil), pil

    img = _to_cv2(image_bytes)

    if do_resize:
        img = resize(img)
    if do_denoise:
        img = denoise(img)

    gray = to_grayscale(img)

    if do_contrast:
        gray = enhance_contrast(gray)
    if do_deskew:
        gray = deskew(gray)
    if do_binarize:
        gray = binarize(gray)
    if do_border:
        gray = add_border(gray)

    pil = Image.fromarray(gray)
    return gray, pil
