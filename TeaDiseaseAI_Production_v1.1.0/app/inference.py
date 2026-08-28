from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

from .config import settings

_model = None
_model_lock = threading.Lock()
_model_path_loaded: Path | None = None
_model_sha256: str | None = None


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def choose_model_path() -> Path | None:
    # Prefer the PyTorch checkpoint for parity with the validated benchmark.
    if settings.model_path.exists():
        return settings.model_path
    if settings.onnx_path.exists():
        return settings.onnx_path
    return None


def model_status() -> dict[str, Any]:
    path = choose_model_path()
    return {
        "available": bool(path),
        "path": str(path) if path else None,
        "format": path.suffix.lower().lstrip(".") if path else None,
        "version": settings.model_version,
        "sha256": file_sha256(path) if path else None,
        "local_validation_status": settings.local_validation_status,
    }


def _get_model():
    global _model, _model_path_loaded, _model_sha256
    path = choose_model_path()
    if path is None:
        raise RuntimeError("Tea disease model file not found. Copy the validated .pt or .onnx file into models/tea_disease/v1.0.0.")
    with _model_lock:
        if _model is None or _model_path_loaded != path:
            from ultralytics import YOLO

            _model = YOLO(str(path))
            _model_path_loaded = path
            _model_sha256 = file_sha256(path)
    return _model


def predict(image_path: Path) -> dict[str, Any]:
    model = _get_model()
    device = settings.inference_device
    kwargs = {"source": str(image_path), "imgsz": 640, "verbose": False}
    if device and device != "auto":
        kwargs["device"] = device
    results = model.predict(**kwargs)
    if not results:
        raise RuntimeError("Model returned no prediction result")
    result = results[0]
    probs = result.probs
    if probs is None:
        raise RuntimeError("Loaded model did not return classification probabilities")

    scores = probs.data.detach().cpu().tolist()
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    top3 = [
        {"class": result.names[int(i)], "confidence": float(scores[int(i)])}
        for i in ranked[:3]
    ]
    top1 = top3[0]
    top2 = top3[1] if len(top3) > 1 else {"class": None, "confidence": 0.0}
    margin = float(top1["confidence"] - top2["confidence"])
    reasons: list[str] = []
    if top1["confidence"] < settings.review_confidence_threshold:
        reasons.append("confidence below review threshold")
    if margin < settings.review_margin_threshold:
        reasons.append("top predictions are too close")

    return {
        "predicted_class": top1["class"],
        "confidence": float(top1["confidence"]),
        "second_class": top2["class"],
        "second_confidence": float(top2["confidence"]),
        "top3": top3,
        "margin": margin,
        "review_recommended": bool(reasons),
        "review_reason": "; ".join(reasons) if reasons else None,
        "model_version": settings.model_version,
        "model_sha256": _model_sha256,
    }
