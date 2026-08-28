from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_name = os.getenv("APP_NAME", "TeaGuard AI")
    company_name = os.getenv("COMPANY_NAME", "Customer Organisation")
    app_version = os.getenv("APP_VERSION", "1.1.0")
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'teaguard.db').as_posix()}")
    upload_dir = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
    session_hours = int(os.getenv("SESSION_HOURS", "12"))
    cookie_secure = _env_bool("COOKIE_SECURE", False)
    model_version = os.getenv("MODEL_VERSION", "tea_disease_yolo26n_v1.0.0")
    model_path = Path(
        os.getenv(
            "MODEL_PATH",
            str(BASE_DIR / "models" / "tea_disease" / "v1.0.0" / "tea_disease_yolo26n_v1.0.0.pt"),
        )
    )
    onnx_path = Path(
        os.getenv(
            "ONNX_PATH",
            str(BASE_DIR / "models" / "tea_disease" / "v1.0.0" / "tea_disease_yolo26n_v1.0.0.onnx"),
        )
    )
    inference_device = os.getenv("INFERENCE_DEVICE", "auto")
    review_confidence_threshold = float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.75"))
    review_margin_threshold = float(os.getenv("REVIEW_MARGIN_THRESHOLD", "0.20"))

    # OpenCV capture-quality gate. These are image-quality heuristics, not disease thresholds.
    quality_min_hard_side = int(os.getenv("QUALITY_MIN_HARD_SIDE", "320"))
    quality_min_recommended_side = int(os.getenv("QUALITY_MIN_RECOMMENDED_SIDE", "640"))
    quality_blur_hard_threshold = float(os.getenv("QUALITY_BLUR_HARD_THRESHOLD", "25"))
    quality_blur_warn_threshold = float(os.getenv("QUALITY_BLUR_WARN_THRESHOLD", "80"))
    quality_brightness_hard_low = float(os.getenv("QUALITY_BRIGHTNESS_HARD_LOW", "20"))
    quality_brightness_warn_low = float(os.getenv("QUALITY_BRIGHTNESS_WARN_LOW", "45"))
    quality_brightness_warn_high = float(os.getenv("QUALITY_BRIGHTNESS_WARN_HIGH", "220"))
    quality_brightness_hard_high = float(os.getenv("QUALITY_BRIGHTNESS_HARD_HIGH", "245"))
    quality_dark_pixel_threshold = int(os.getenv("QUALITY_DARK_PIXEL_THRESHOLD", "28"))
    quality_bright_pixel_threshold = int(os.getenv("QUALITY_BRIGHT_PIXEL_THRESHOLD", "245"))
    quality_clip_warn_ratio = float(os.getenv("QUALITY_CLIP_WARN_RATIO", "0.35"))
    quality_clip_hard_ratio = float(os.getenv("QUALITY_CLIP_HARD_RATIO", "0.80"))
    quality_contrast_warn_threshold = float(os.getenv("QUALITY_CONTRAST_WARN_THRESHOLD", "18"))
    quality_leaf_coverage_warn_threshold = float(os.getenv("QUALITY_LEAF_COVERAGE_WARN_THRESHOLD", "0.05"))
    quality_center_coverage_warn_threshold = float(os.getenv("QUALITY_CENTER_COVERAGE_WARN_THRESHOLD", "0.03"))
    quality_score_hard_min = float(os.getenv("QUALITY_SCORE_HARD_MIN", "35"))
    quality_inference_max_side = int(os.getenv("QUALITY_INFERENCE_MAX_SIDE", "1600"))
    quality_max_input_megapixels = float(os.getenv("QUALITY_MAX_INPUT_MEGAPIXELS", "50"))

    local_validation_status = os.getenv(
        "LOCAL_VALIDATION_STATUS",
        "Customer field validation pending",
    )


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
(settings.upload_dir / "original").mkdir(parents=True, exist_ok=True)
(settings.upload_dir / "processed").mkdir(parents=True, exist_ok=True)
(settings.upload_dir / "_quality_checks").mkdir(parents=True, exist_ok=True)
