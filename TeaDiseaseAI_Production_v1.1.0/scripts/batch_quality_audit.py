from __future__ import annotations

import argparse
import csv
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from app.vision_quality import assess_and_prepare, quality_runtime_status

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-audit field images with TeaGuard OpenCV capture-quality rules.")
    parser.add_argument("--input", required=True, help="Folder containing field images")
    parser.add_argument("--output", required=True, help="Output folder for CSV/JSON report")
    args = parser.parse_args()

    source = Path(args.input).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        raise SystemExit(f"Input folder not found: {source}")

    images = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    rows: list[dict] = []
    grades = Counter()

    with tempfile.TemporaryDirectory(prefix="teaguard_quality_") as tmpdir:
        tmp = Path(tmpdir)
        for idx, image in enumerate(images, 1):
            processed = tmp / f"{idx:06d}.jpg"
            try:
                q = assess_and_prepare(image, processed)
                d = q.to_dict()
                grades[d["grade"]] += 1
                rows.append({
                    "image": str(image),
                    "passed": d["passed"],
                    "grade": d["grade"],
                    "quality_score": d["quality_score"],
                    "width": d["width"],
                    "height": d["height"],
                    "blur_variance": d["blur_variance"],
                    "brightness_mean": d["brightness_mean"],
                    "dark_ratio": d["dark_ratio"],
                    "bright_ratio": d["bright_ratio"],
                    "contrast_std": d["contrast_std"],
                    "saturation_mean": d["saturation_mean"],
                    "leaf_like_coverage": d["leaf_like_coverage"],
                    "center_leaf_like_coverage": d["center_leaf_like_coverage"],
                    "hard_fail_reasons": "; ".join(d["hard_fail_reasons"]),
                    "warnings": "; ".join(d["warnings"]),
                    "error": "",
                })
            except Exception as exc:
                rows.append({"image": str(image), "passed": False, "grade": "ERROR", "error": str(exc)})
                grades["ERROR"] += 1

    fields = [
        "image", "passed", "grade", "quality_score", "width", "height", "blur_variance",
        "brightness_mean", "dark_ratio", "bright_ratio", "contrast_std", "saturation_mean",
        "leaf_like_coverage", "center_leaf_like_coverage", "hard_fail_reasons", "warnings", "error",
    ]
    with (out / "capture_quality_audit.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    valid_scores = [float(r["quality_score"]) for r in rows if r.get("quality_score") not in (None, "")]
    summary = {
        "engine": quality_runtime_status(),
        "input_folder": str(source),
        "images": len(images),
        "processed": len(rows),
        "passed": sum(1 for r in rows if r.get("passed") is True),
        "rejected_or_error": sum(1 for r in rows if r.get("passed") is not True),
        "grade_counts": dict(grades),
        "average_quality_score": round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None,
        "note": "Capture-quality audit only; no disease inference, lesion segmentation or severity estimation was performed.",
    }
    (out / "capture_quality_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"CSV: {out / 'capture_quality_audit.csv'}")
    print(f"JSON: {out / 'capture_quality_summary.json'}")


if __name__ == "__main__":
    main()
