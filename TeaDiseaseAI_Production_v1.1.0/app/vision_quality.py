from __future__ import annotations

"""OpenCV capture-quality engine for TeaGuard AI.

This module deliberately evaluates *capture quality*, not disease severity or diagnosis.
It is conservative by design: hard rejections are reserved for gross failures such as
very low resolution, severe blur, or extreme exposure. Leaf-like coverage is advisory
only because field backgrounds and diseased leaves can vary substantially.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import settings

ENGINE_VERSION = "opencv_capture_quality_v1.0.0"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _linear_score(value: float, bad: float, good: float) -> float:
    if good == bad:
        return 1.0
    return _clamp((value - bad) / (good - bad))


def _brightness_score(mean_value: float, dark_ratio: float, bright_ratio: float) -> float:
    # Peak around a neutral midtone; clipping penalizes heavily.
    tonal = 1.0 - _clamp(abs(mean_value - 135.0) / 120.0)
    clipping_penalty = _clamp(max(dark_ratio, bright_ratio) / 0.45)
    return _clamp(tonal * (1.0 - 0.65 * clipping_penalty))


def _largest_leaf_like_coverage(bgr: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Return broad leaf-like subject coverage estimates.

    The mask intentionally includes green, yellow and brown chromatic regions so that
    diseased tissue is not excluded. It is *not* a segmentation model and is never
    used as a disease measurement.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Broad vegetation / tea-tissue colour envelope in OpenCV HSV space.
    chromatic = (s >= 32) & (v >= 24)
    hue_like_leaf = ((h >= 4) & (h <= 105))
    mask = (chromatic & hue_like_leaf).astype(np.uint8) * 255

    # Remove speckle and bridge small gaps. Kernel scales mildly with image size.
    short_side = min(bgr.shape[:2])
    k = max(3, min(11, (short_side // 260) * 2 + 1))
    kernel = np.ones((k, k), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total = float(bgr.shape[0] * bgr.shape[1])
    largest = 0.0
    if contours:
        largest = max(cv2.contourArea(c) for c in contours) / max(total, 1.0)

    hgt, wdt = bgr.shape[:2]
    y1, y2 = int(hgt * 0.25), int(hgt * 0.75)
    x1, x2 = int(wdt * 0.25), int(wdt * 0.75)
    centre = mask[y1:y2, x1:x2]
    centre_cov = float(np.count_nonzero(centre)) / max(float(centre.size), 1.0)
    return float(largest), float(centre_cov), mask


@dataclass
class QualityResult:
    engine_version: str
    passed: bool
    grade: str
    quality_score: float
    hard_fail_reasons: list[str]
    warnings: list[str]
    width: int
    height: int
    processed_width: int
    processed_height: int
    blur_variance: float
    brightness_mean: float
    dark_ratio: float
    bright_ratio: float
    contrast_std: float
    saturation_mean: float
    leaf_like_coverage: float
    center_leaf_like_coverage: float
    preprocessing: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_and_prepare(source_path: Path, processed_path: Path) -> QualityResult:
    source_path = Path(source_path)
    processed_path = Path(processed_path)
    bgr = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if bgr is None or bgr.size == 0:
        raise ValueError("OpenCV could not decode the normalized image")

    height, width = bgr.shape[:2]
    short_side = min(width, height)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_mean = float(gray.mean())
    contrast_std = float(gray.std())
    dark_ratio = float(np.mean(gray <= settings.quality_dark_pixel_threshold))
    bright_ratio = float(np.mean(gray >= settings.quality_bright_pixel_threshold))
    saturation_mean = float(hsv[:, :, 1].mean())
    leaf_cov, centre_cov, _ = _largest_leaf_like_coverage(bgr)

    hard: list[str] = []
    warnings: list[str] = []

    if short_side < settings.quality_min_hard_side:
        hard.append(f"resolution too low ({width}×{height}; minimum short side {settings.quality_min_hard_side}px)")
    elif short_side < settings.quality_min_recommended_side:
        warnings.append(f"resolution below recommended {settings.quality_min_recommended_side}px short side")

    if blur_variance < settings.quality_blur_hard_threshold:
        hard.append("image is severely blurred or lacks usable edge detail")
    elif blur_variance < settings.quality_blur_warn_threshold:
        warnings.append("image may be slightly out of focus; retake closer and steadier if possible")

    if brightness_mean < settings.quality_brightness_hard_low or dark_ratio > settings.quality_clip_hard_ratio:
        hard.append("image is severely underexposed")
    elif brightness_mean < settings.quality_brightness_warn_low or dark_ratio > settings.quality_clip_warn_ratio:
        warnings.append("image is dark; use brighter natural light without flash glare")

    if brightness_mean > settings.quality_brightness_hard_high or bright_ratio > settings.quality_clip_hard_ratio:
        hard.append("image is severely overexposed")
    elif brightness_mean > settings.quality_brightness_warn_high or bright_ratio > settings.quality_clip_warn_ratio:
        warnings.append("image is bright or clipped; avoid direct glare on the leaf")

    if contrast_std < settings.quality_contrast_warn_threshold:
        warnings.append("low local contrast; symptoms may be difficult to see")

    # Advisory only. This is a broad colour/subject heuristic, not leaf segmentation.
    if leaf_cov < settings.quality_leaf_coverage_warn_threshold:
        warnings.append("leaf-like subject coverage appears low; fill more of the frame with one main leaf")
    if centre_cov < settings.quality_center_coverage_warn_threshold:
        warnings.append("main leaf may not be centred; place the leaf near the centre of the frame")

    sharpness_score = _linear_score(blur_variance, settings.quality_blur_hard_threshold, 220.0)
    resolution_score = _linear_score(short_side, settings.quality_min_hard_side, 1000.0)
    contrast_score = _linear_score(contrast_std, 10.0, 45.0)
    subject_score = _linear_score(leaf_cov, 0.03, 0.38)
    brightness_score = _brightness_score(brightness_mean, dark_ratio, bright_ratio)

    score = 100.0 * (
        0.34 * sharpness_score
        + 0.24 * brightness_score
        + 0.16 * resolution_score
        + 0.16 * contrast_score
        + 0.10 * subject_score
    )
    score = round(_clamp(score / 100.0) * 100.0, 1)

    if not hard and score < settings.quality_score_hard_min:
        hard.append("overall capture quality is too low for reliable screening")

    passed = not hard
    if not passed:
        grade = "Fail"
    elif score >= 82:
        grade = "Excellent"
    elif score >= 67:
        grade = "Good"
    elif score >= 50:
        grade = "Fair"
    else:
        grade = "Poor"

    # Safe preprocessing: preserve colour; only downscale with area interpolation.
    # No CLAHE, white-balance or lesion enhancement is applied until validated on
    # local estate images, because colour manipulation can alter disease cues.
    processed = bgr
    max_side = max(width, height)
    scale = 1.0
    if max_side > settings.quality_inference_max_side:
        scale = settings.quality_inference_max_side / float(max_side)
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        processed = cv2.resize(bgr, new_size, interpolation=cv2.INTER_AREA)

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(processed_path), processed, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    if not ok:
        raise OSError(f"Could not save processed inference image: {processed_path}")

    ph, pw = processed.shape[:2]
    return QualityResult(
        engine_version=ENGINE_VERSION,
        passed=passed,
        grade=grade,
        quality_score=score,
        hard_fail_reasons=hard,
        warnings=warnings,
        width=int(width),
        height=int(height),
        processed_width=int(pw),
        processed_height=int(ph),
        blur_variance=round(blur_variance, 2),
        brightness_mean=round(brightness_mean, 2),
        dark_ratio=round(dark_ratio, 4),
        bright_ratio=round(bright_ratio, 4),
        contrast_std=round(contrast_std, 2),
        saturation_mean=round(saturation_mean, 2),
        leaf_like_coverage=round(leaf_cov, 4),
        center_leaf_like_coverage=round(centre_cov, 4),
        preprocessing={
            "exif_orientation_corrected_before_opencv": True,
            "colour_transformation": "none",
            "resize_only": bool(scale < 1.0),
            "resize_scale": round(scale, 6),
            "interpolation": "INTER_AREA" if scale < 1.0 else "none",
            "jpeg_quality": 94,
            "inference_max_side": settings.quality_inference_max_side,
            "note": "Capture-quality processing only; no disease segmentation or severity estimation.",
        },
    )


def quality_runtime_status() -> dict[str, Any]:
    return {
        "available": True,
        "engine": ENGINE_VERSION,
        "opencv_version": cv2.__version__,
        "hard_gate": {
            "min_short_side_px": settings.quality_min_hard_side,
            "blur_variance_min": settings.quality_blur_hard_threshold,
            "brightness_mean_low": settings.quality_brightness_hard_low,
            "brightness_mean_high": settings.quality_brightness_hard_high,
            "extreme_clip_ratio": settings.quality_clip_hard_ratio,
            "min_overall_score": settings.quality_score_hard_min,
            "max_input_megapixels": settings.quality_max_input_megapixels,
        },
        "advisory": {
            "recommended_short_side_px": settings.quality_min_recommended_side,
            "blur_warn_below": settings.quality_blur_warn_threshold,
            "leaf_like_coverage_warn_below": settings.quality_leaf_coverage_warn_threshold,
            "center_coverage_warn_below": settings.quality_center_coverage_warn_threshold,
        },
        "scope_note": "These thresholds assess capture quality only. They do not validate disease diagnosis or severity and should be calibrated using local customer devices and field images.",
    }
