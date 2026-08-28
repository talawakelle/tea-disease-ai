from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.vision_quality import assess_and_prepare, quality_runtime_status


def make_leaf() -> np.ndarray:
    h, w = 900, 1200
    img = np.full((h, w, 3), (155, 170, 160), dtype=np.uint8)
    cv2.ellipse(img, (600, 450), (360, 230), -8, 0, 360, (45, 125, 55), -1)
    cv2.line(img, (280, 510), (930, 395), (150, 205, 150), 10)
    for y in range(330, 620, 65):
        cv2.line(img, (600, y), (430, y - 80), (120, 180, 120), 4)
        cv2.line(img, (620, y), (800, y - 80), (120, 180, 120), 4)
    return img


with tempfile.TemporaryDirectory(prefix="teaguard_opencv_selftest_") as td:
    root = Path(td)
    good = root / "good.jpg"
    good_out = root / "good_processed.jpg"
    cv2.imwrite(str(good), make_leaf())
    q = assess_and_prepare(good, good_out)
    assert q.passed, q
    assert good_out.exists()

    tiny = root / "tiny.jpg"
    tiny_out = root / "tiny_processed.jpg"
    cv2.imwrite(str(tiny), cv2.resize(make_leaf(), (180, 130)))
    q2 = assess_and_prepare(tiny, tiny_out)
    assert not q2.passed, q2

print("OPENCV SELF-TEST: PASSED")
print(quality_runtime_status())
