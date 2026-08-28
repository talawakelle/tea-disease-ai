from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.vision_quality import assess_and_prepare


def _synthetic_leaf(width: int = 1400, height: int = 1000) -> np.ndarray:
    rng = np.random.default_rng(7)
    img = np.full((height, width, 3), (155, 170, 160), dtype=np.uint8)
    noise = rng.normal(0, 7, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    cv2.ellipse(img, (width // 2, height // 2), (420, 250), -8, 0, 360, (45, 125, 55), -1)
    cv2.line(img, (300, 560), (1100, 440), (150, 205, 150), 10)
    for y in range(350, 650, 70):
        cv2.line(img, (680, y), (470, y - 80), (120, 180, 120), 4)
        cv2.line(img, (720, y), (930, y - 80), (120, 180, 120), 4)
    for centre in [(620, 450), (780, 520), (850, 410)]:
        cv2.circle(img, centre, 35, (55, 75, 120), -1)
    return img


def test_good_capture_passes_and_preserves_colour(tmp_path: Path) -> None:
    source = tmp_path / "good.jpg"
    processed = tmp_path / "processed.jpg"
    cv2.imwrite(str(source), _synthetic_leaf())
    q = assess_and_prepare(source, processed)
    assert q.passed is True
    assert q.grade in {"Excellent", "Good"}
    assert q.quality_score >= 67
    assert q.preprocessing["colour_transformation"] == "none"
    assert processed.exists()


def test_tiny_capture_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "tiny.jpg"
    processed = tmp_path / "processed.jpg"
    tiny = cv2.resize(_synthetic_leaf(), (180, 130))
    cv2.imwrite(str(source), tiny)
    q = assess_and_prepare(source, processed)
    assert q.passed is False
    assert q.grade == "Fail"
    assert any("resolution too low" in x for x in q.hard_fail_reasons)


def test_dark_flat_capture_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "dark.jpg"
    processed = tmp_path / "processed.jpg"
    cv2.imwrite(str(source), np.full((800, 1000, 3), 8, dtype=np.uint8))
    q = assess_and_prepare(source, processed)
    assert q.passed is False
    assert any("underexposed" in x for x in q.hard_fail_reasons)
