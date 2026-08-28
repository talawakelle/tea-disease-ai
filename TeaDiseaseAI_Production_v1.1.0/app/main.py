from __future__ import annotations

import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field as PydField
from sqlalchemy import func, select

from .config import BASE_DIR, settings
from .database import (
    AuditEvent,
    Division,
    Estate,
    Field,
    Prediction,
    QualityAssessment,
    SessionLocal,
    SystemSetting,
    User,
    init_db,
    utcnow,
)
from .inference import model_status, predict
from .vision_quality import assess_and_prepare, quality_runtime_status
from .security import SESSION_COOKIE, create_session, delete_session, hash_password, resolve_session, verify_password

FRONTEND = BASE_DIR / "frontend"
ALLOWED_ROLES = {"owner", "admin", "reviewer", "operator", "viewer"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_API = {"/api/health", "/api/setup/status", "/api/setup", "/api/auth/login"}

app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


class SetupPayload(BaseModel):
    company_name: str = PydField(min_length=2, max_length=150)
    display_name: str = PydField(min_length=2, max_length=150)
    username: str = PydField(min_length=3, max_length=100)
    password: str = PydField(min_length=10, max_length=200)


class LoginPayload(BaseModel):
    username: str = PydField(min_length=1, max_length=100)
    password: str = PydField(min_length=1, max_length=200)


class UserCreatePayload(BaseModel):
    username: str = PydField(min_length=3, max_length=100)
    display_name: str = PydField(min_length=2, max_length=150)
    password: str = PydField(min_length=10, max_length=200)
    role: str = PydField(default="operator")


class LocationPayload(BaseModel):
    name: str = PydField(min_length=1, max_length=150)


class DivisionPayload(BaseModel):
    estate_id: int
    name: str = PydField(min_length=1, max_length=150)


class FieldPayload(BaseModel):
    division_id: int
    field_code: str = PydField(min_length=1, max_length=100)
    hectares: float | None = None
    clone: str | None = PydField(default=None, max_length=100)


class ReviewPayload(BaseModel):
    status: str = PydField(pattern="^(confirmed|corrected|rejected)$")
    reviewed_class: str | None = PydField(default=None, max_length=100)
    notes: str | None = PydField(default=None, max_length=3000)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def security_and_auth(request: Request, call_next):
    path = request.url.path
    user = None
    csrf = None
    if path.startswith("/api") and path not in PUBLIC_API and not path.startswith("/api/docs") and not path.startswith("/openapi.json"):
        user, csrf = resolve_session(request.cookies.get(SESSION_COOKIE))
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        request.state.user = user
        request.state.csrf = csrf
        if request.method in MUTATING:
            sent = request.headers.get("X-CSRF-Token")
            if not sent or not secrets.compare_digest(sent, csrf or ""):
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


def _user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _require(request: Request, roles: set[str]) -> User:
    user = _user(request)
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return user


def _audit(user_id: int | None, event_type: str, entity_type: str | None = None, entity_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    with SessionLocal() as db:
        db.add(
            AuditEvent(
                user_id=user_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=json.dumps(details or {}, ensure_ascii=False),
            )
        )
        db.commit()


def _quality_dict(row: QualityAssessment | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "engine_version": row.engine_version,
        "passed": row.passed,
        "grade": row.grade,
        "quality_score": row.quality_score,
        "warnings": json.loads(row.warnings_json or "[]"),
        "hard_fail_reasons": json.loads(row.hard_fail_reasons_json or "[]"),
        "width": row.original_width,
        "height": row.original_height,
        "processed_width": row.processed_width,
        "processed_height": row.processed_height,
        "blur_variance": row.blur_variance,
        "brightness_mean": row.brightness_mean,
        "dark_ratio": row.dark_ratio,
        "bright_ratio": row.bright_ratio,
        "contrast_std": row.contrast_std,
        "saturation_mean": row.saturation_mean,
        "leaf_like_coverage": row.leaf_like_coverage,
        "center_leaf_like_coverage": row.center_leaf_like_coverage,
        "preprocessing": json.loads(row.preprocessing_json or "{}"),
    }


def _prediction_dict(row: Prediction) -> dict[str, Any]:
    quality = _quality_dict(getattr(row, "quality_assessment", None))
    return {
        "id": row.id,
        "scan_ref": row.scan_ref,
        "predicted_class": row.predicted_class,
        "confidence": row.confidence,
        "second_class": row.second_class,
        "second_confidence": row.second_confidence,
        "top3": json.loads(row.top3_json),
        "model_version": row.model_version,
        "model_sha256": row.model_sha256,
        "review_recommended": row.review_recommended,
        "review_reason": row.review_reason,
        "review_status": row.review_status,
        "reviewed_class": row.reviewed_class,
        "reviewer_notes": row.reviewer_notes,
        "capture_notes": row.capture_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "estate": row.estate.name if row.estate else None,
        "estate_id": row.estate_id,
        "division": row.division.name if row.division else None,
        "division_id": row.division_id,
        "field": row.field.field_code if row.field else None,
        "field_id": row.field_id,
        "image_url": f"/api/predictions/{row.id}/image",
        "processed_image_url": f"/api/predictions/{row.id}/processed-image" if quality else None,
        "quality": quality,
    }


@app.get("/", response_class=HTMLResponse)
def root() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(FRONTEND / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js")
def service_worker() -> FileResponse:
    return FileResponse(FRONTEND / "service-worker.js", media_type="application/javascript")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version, "model": model_status(), "capture_quality": quality_runtime_status()}


def _system_value(db, key: str, default: str) -> str:
    row = db.get(SystemSetting, key)
    return row.value if row else default


def _set_system_value(db, key: str, value: str) -> None:
    row = db.get(SystemSetting, key)
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


@app.get("/api/setup/status")
def setup_status() -> dict[str, Any]:
    with SessionLocal() as db:
        count = db.scalar(select(func.count(User.id))) or 0
        company = _system_value(db, "company_name", settings.company_name)
    return {"setup_required": count == 0, "app_name": settings.app_name, "company_name": company}


@app.post("/api/setup")
def setup(payload: SetupPayload) -> dict[str, Any]:
    with SessionLocal() as db:
        count = db.scalar(select(func.count(User.id))) or 0
        if count:
            raise HTTPException(status_code=409, detail="Initial setup has already been completed")
        user = User(
            username=payload.username.strip().lower(),
            display_name=payload.display_name.strip(),
            role="owner",
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.flush()
        _set_system_value(db, "company_name", payload.company_name.strip())
        db.commit()
        db.refresh(user)
    _audit(user.id, "initial_setup", "user", str(user.id), {"company_name": payload.company_name})
    return {"status": "created", "username": user.username}


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> JSONResponse:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == payload.username.strip().lower())).scalar_one_or_none()
        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        user_id = user.id
        display_name = user.display_name
        role = user.role
    raw, csrf = create_session(user_id)
    _audit(user_id, "login")
    response = JSONResponse({"status": "ok", "user": {"id": user_id, "display_name": display_name, "role": role}, "csrf_token": csrf})
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    user = _user(request)
    delete_session(request.cookies.get(SESSION_COOKIE))
    _audit(user.id, "logout")
    response = JSONResponse({"status": "signed_out"})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/auth/me")
def me(request: Request) -> dict[str, Any]:
    user = _user(request)
    with SessionLocal() as db:
        company = _system_value(db, "company_name", settings.company_name)
    return {
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
        "csrf_token": request.state.csrf,
        "app": {"name": settings.app_name, "company": company, "version": settings.app_version},
    }


@app.get("/api/model/status")
def api_model_status(request: Request) -> dict[str, Any]:
    _user(request)
    return model_status() | {
        "capture_quality": quality_runtime_status(),
        "benchmark": {
            "scope": "Held-out public Sri Lankan tea leaf dataset test split",
            "test_images": 257,
            "accuracy": 0.9844,
            "balanced_accuracy": 0.9843,
            "macro_f1": 0.9861,
            "weighted_f1": 0.9844,
            "note": "This benchmark is not a guarantee of performance on customer field images. Local validation is required.",
        }
    }


@app.get("/api/users")
def users_list(request: Request) -> list[dict[str, Any]]:
    _require(request, {"owner", "admin"})
    with SessionLocal() as db:
        rows = db.execute(select(User).order_by(User.display_name)).scalars().all()
        return [{"id": r.id, "username": r.username, "display_name": r.display_name, "role": r.role, "is_active": r.is_active} for r in rows]


@app.post("/api/users")
def users_create(request: Request, payload: UserCreatePayload) -> dict[str, Any]:
    actor = _require(request, {"owner", "admin"})
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.username == payload.username.strip().lower())).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        user = User(
            username=payload.username.strip().lower(),
            display_name=payload.display_name.strip(),
            role=payload.role,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    _audit(actor.id, "user_created", "user", str(user.id), {"role": user.role})
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}


@app.get("/api/locations")
def locations(request: Request) -> dict[str, Any]:
    _user(request)
    with SessionLocal() as db:
        estates = db.execute(select(Estate).where(Estate.is_active == True).order_by(Estate.name)).scalars().all()
        divisions = db.execute(select(Division).where(Division.is_active == True).order_by(Division.name)).scalars().all()
        fields = db.execute(select(Field).where(Field.is_active == True).order_by(Field.field_code)).scalars().all()
        return {
            "estates": [{"id": x.id, "name": x.name} for x in estates],
            "divisions": [{"id": x.id, "estate_id": x.estate_id, "name": x.name} for x in divisions],
            "fields": [{"id": x.id, "division_id": x.division_id, "field_code": x.field_code, "hectares": x.hectares, "clone": x.clone} for x in fields],
        }


@app.post("/api/locations/estates")
def estate_create(request: Request, payload: LocationPayload) -> dict[str, Any]:
    actor = _require(request, {"owner", "admin"})
    with SessionLocal() as db:
        row = Estate(name=payload.name.strip())
        db.add(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="Estate already exists")
        db.refresh(row)
    _audit(actor.id, "estate_created", "estate", str(row.id))
    return {"id": row.id, "name": row.name}


@app.post("/api/locations/divisions")
def division_create(request: Request, payload: DivisionPayload) -> dict[str, Any]:
    actor = _require(request, {"owner", "admin"})
    with SessionLocal() as db:
        if not db.get(Estate, payload.estate_id):
            raise HTTPException(status_code=404, detail="Estate not found")
        row = Division(estate_id=payload.estate_id, name=payload.name.strip())
        db.add(row)
        db.commit()
        db.refresh(row)
    _audit(actor.id, "division_created", "division", str(row.id))
    return {"id": row.id, "estate_id": row.estate_id, "name": row.name}


@app.post("/api/locations/fields")
def field_create(request: Request, payload: FieldPayload) -> dict[str, Any]:
    actor = _require(request, {"owner", "admin"})
    with SessionLocal() as db:
        if not db.get(Division, payload.division_id):
            raise HTTPException(status_code=404, detail="Division not found")
        row = Field(division_id=payload.division_id, field_code=payload.field_code.strip(), hectares=payload.hectares, clone=(payload.clone or "").strip() or None)
        db.add(row)
        db.commit()
        db.refresh(row)
    _audit(actor.id, "field_created", "field", str(row.id))
    return {"id": row.id, "division_id": row.division_id, "field_code": row.field_code, "hectares": row.hectares, "clone": row.clone}


def _save_normalized_image(data: bytes, dest: Path) -> dict[str, Any]:
    """Validate upload, correct EXIF orientation, preserve colour, and save audit image."""
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds {settings.max_upload_mb} MB limit")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if (image.width * image.height) > int(settings.quality_max_input_megapixels * 1_000_000):
                raise HTTPException(status_code=413, detail=f"Image dimensions exceed {settings.quality_max_input_megapixels:g} megapixel safety limit")
            corrected = ImageOps.exif_transpose(image)
            rgb = corrected.convert("RGB")
            # Audit image may be bounded for storage, but remains higher resolution than inference input.
            max_side = 2600
            if max(rgb.size) > max_side:
                scale = max_side / max(rgb.size)
                rgb = rgb.resize((max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale))), Image.Resampling.LANCZOS)
            width, height = rgb.size
            dest.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(dest, format="JPEG", quality=94, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")
    return {"sha256": hashlib.sha256(data).hexdigest(), "width": width, "height": height}


@app.post("/api/quality/check")
async def quality_check_api(request: Request, image: UploadFile = File(...)) -> dict[str, Any]:
    _require(request, {"owner", "admin", "reviewer", "operator"})
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")
    raw = await image.read()
    token = secrets.token_hex(8)
    original = settings.upload_dir / "_quality_checks" / f"{token}_original.jpg"
    processed = settings.upload_dir / "_quality_checks" / f"{token}_processed.jpg"
    try:
        _save_normalized_image(raw, original)
        result = assess_and_prepare(original, processed).to_dict()
        return result | {"scope": "capture_quality_only", "disease_inference_ran": False}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"OpenCV quality engine failed: {exc}")
    finally:
        original.unlink(missing_ok=True)
        processed.unlink(missing_ok=True)


@app.post("/api/predict")
async def predict_api(
    request: Request,
    image: UploadFile = File(...),
    estate_id: int | None = Form(default=None),
    division_id: int | None = Form(default=None),
    field_id: int | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> dict[str, Any]:
    user = _require(request, {"owner", "admin", "reviewer", "operator"})
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    raw = await image.read()
    scan_ref = f"TG-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    original_dest = settings.upload_dir / "original" / f"{scan_ref}.jpg"
    processed_dest = settings.upload_dir / "processed" / f"{scan_ref}.jpg"
    image_meta = _save_normalized_image(raw, original_dest)

    with SessionLocal() as db:
        estate = db.get(Estate, estate_id) if estate_id else None
        division = db.get(Division, division_id) if division_id else None
        field = db.get(Field, field_id) if field_id else None
        if division and estate and division.estate_id != estate.id:
            original_dest.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Division does not belong to selected estate")
        if field and division and field.division_id != division.id:
            original_dest.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Field does not belong to selected division")

    try:
        quality = assess_and_prepare(original_dest, processed_dest)
    except Exception as exc:
        original_dest.unlink(missing_ok=True)
        processed_dest.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=f"OpenCV quality engine failed: {exc}")

    if not quality.passed:
        details = quality.to_dict()
        _audit(user.id, "capture_quality_rejected", "scan_attempt", scan_ref, details)
        original_dest.unlink(missing_ok=True)
        processed_dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CAPTURE_QUALITY_REJECTED",
                "message": "Image quality is too low for AI screening. Please retake the photo.",
                "quality": details,
            },
        )

    try:
        result = predict(processed_dest)
    except Exception as exc:
        original_dest.unlink(missing_ok=True)
        processed_dest.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc))

    # A fair/poor capture or material quality warning raises human review priority.
    quality_review = quality.grade in {"Fair", "Poor"}
    quality_review_reason = None
    if quality_review:
        quality_review_reason = f"capture quality grade {quality.grade.lower()} ({quality.quality_score:.1f}/100)"

    model_review = bool(result["review_recommended"])
    review_reasons = [x for x in [result.get("review_reason"), quality_review_reason] if x]
    review_recommended = bool(model_review or quality_review)
    review_reason = "; ".join(review_reasons) if review_reasons else None

    with SessionLocal() as db:
        row = Prediction(
            scan_ref=scan_ref,
            user_id=user.id,
            estate_id=estate_id,
            division_id=division_id,
            field_id=field_id,
            image_path=str(original_dest),
            image_sha256=image_meta["sha256"],
            predicted_class=result["predicted_class"],
            confidence=result["confidence"],
            second_class=result["second_class"],
            second_confidence=result["second_confidence"],
            top3_json=json.dumps(result["top3"]),
            model_version=result["model_version"],
            model_sha256=result["model_sha256"],
            review_recommended=review_recommended,
            review_reason=review_reason,
            capture_notes=(notes or "").strip() or None,
        )
        db.add(row)
        db.flush()
        q = QualityAssessment(
            prediction_id=row.id,
            engine_version=quality.engine_version,
            original_path=str(original_dest),
            processed_path=str(processed_dest),
            original_width=quality.width,
            original_height=quality.height,
            processed_width=quality.processed_width,
            processed_height=quality.processed_height,
            quality_score=quality.quality_score,
            grade=quality.grade,
            passed=quality.passed,
            hard_fail_reasons_json=json.dumps(quality.hard_fail_reasons),
            warnings_json=json.dumps(quality.warnings),
            blur_variance=quality.blur_variance,
            brightness_mean=quality.brightness_mean,
            dark_ratio=quality.dark_ratio,
            bright_ratio=quality.bright_ratio,
            contrast_std=quality.contrast_std,
            saturation_mean=quality.saturation_mean,
            leaf_like_coverage=quality.leaf_like_coverage,
            center_leaf_like_coverage=quality.center_leaf_like_coverage,
            preprocessing_json=json.dumps(quality.preprocessing),
        )
        db.add(q)
        db.commit()
        db.refresh(row)
        db.refresh(row, attribute_names=["estate", "division", "field", "quality_assessment"])
        out = _prediction_dict(row)

    _audit(
        user.id,
        "prediction_created",
        "prediction",
        str(out["id"]),
        {
            "scan_ref": scan_ref,
            "predicted_class": out["predicted_class"],
            "confidence": out["confidence"],
            "capture_quality_score": quality.quality_score,
            "capture_quality_grade": quality.grade,
            "quality_engine": quality.engine_version,
        },
    )
    return out


@app.get("/api/predictions")
def predictions_list(request: Request, limit: int = 100, review_only: bool = False) -> list[dict[str, Any]]:
    _user(request)
    limit = min(max(limit, 1), 500)
    with SessionLocal() as db:
        query = select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)
        if review_only:
            query = select(Prediction).where(Prediction.review_recommended == True, Prediction.review_status == "unreviewed").order_by(Prediction.created_at.desc()).limit(limit)
        rows = db.execute(query).scalars().all()
        for row in rows:
            _ = row.estate, row.division, row.field
        return [_prediction_dict(row) for row in rows]


@app.get("/api/predictions/{prediction_id}")
def prediction_get(request: Request, prediction_id: int) -> dict[str, Any]:
    _user(request)
    with SessionLocal() as db:
        row = db.get(Prediction, prediction_id)
        if not row:
            raise HTTPException(status_code=404, detail="Prediction not found")
        _ = row.estate, row.division, row.field
        return _prediction_dict(row)


@app.get("/api/predictions/{prediction_id}/image")
def prediction_image(request: Request, prediction_id: int) -> FileResponse:
    _user(request)
    with SessionLocal() as db:
        row = db.get(Prediction, prediction_id)
        if not row:
            raise HTTPException(status_code=404, detail="Prediction not found")
        path = Path(row.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/predictions/{prediction_id}/processed-image")
def prediction_processed_image(request: Request, prediction_id: int) -> FileResponse:
    _user(request)
    with SessionLocal() as db:
        q = db.execute(select(QualityAssessment).where(QualityAssessment.prediction_id == prediction_id)).scalar_one_or_none()
        if not q:
            raise HTTPException(status_code=404, detail="Processed image not found")
        path = Path(q.processed_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed image file not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/predictions/{prediction_id}/review")
def prediction_review(request: Request, prediction_id: int, payload: ReviewPayload) -> dict[str, Any]:
    reviewer = _require(request, {"owner", "admin", "reviewer"})
    with SessionLocal() as db:
        row = db.get(Prediction, prediction_id)
        if not row:
            raise HTTPException(status_code=404, detail="Prediction not found")
        if payload.status == "corrected" and not payload.reviewed_class:
            raise HTTPException(status_code=400, detail="Corrected review requires the confirmed class")
        row.review_status = payload.status
        row.reviewed_class = payload.reviewed_class if payload.status == "corrected" else (row.predicted_class if payload.status == "confirmed" else None)
        row.reviewer_notes = (payload.notes or "").strip() or None
        row.reviewed_by = reviewer.id
        row.reviewed_at = utcnow()
        db.commit()
        db.refresh(row)
        _ = row.estate, row.division, row.field
        out = _prediction_dict(row)
    _audit(reviewer.id, "prediction_reviewed", "prediction", str(prediction_id), {"status": payload.status, "reviewed_class": out["reviewed_class"]})
    return out


@app.get("/api/dashboard")
def dashboard(request: Request) -> dict[str, Any]:
    _user(request)
    with SessionLocal() as db:
        total = db.scalar(select(func.count(Prediction.id))) or 0
        review = db.scalar(select(func.count(Prediction.id)).where(Prediction.review_recommended == True, Prediction.review_status == "unreviewed")) or 0
        avg_conf = db.scalar(select(func.avg(Prediction.confidence))) or 0.0
        avg_quality = db.scalar(select(func.avg(QualityAssessment.quality_score))) or 0.0
        quality_review_count = db.scalar(
            select(func.count(QualityAssessment.id)).where(QualityAssessment.grade.in_(["Fair", "Poor", "Fail"]))
        ) or 0
        disease_rows = db.execute(select(Prediction.predicted_class, func.count(Prediction.id)).group_by(Prediction.predicted_class).order_by(func.count(Prediction.id).desc())).all()
        estate_rows = db.execute(
            select(Estate.name, func.count(Prediction.id))
            .join(Prediction, Prediction.estate_id == Estate.id)
            .group_by(Estate.name)
            .order_by(func.count(Prediction.id).desc())
            .limit(8)
        ).all()
        recent = db.execute(select(Prediction).order_by(Prediction.created_at.desc()).limit(8)).scalars().all()
        for row in recent:
            _ = row.estate, row.division, row.field
        return {
            "total_scans": total,
            "review_queue": review,
            "average_confidence": float(avg_conf),
            "average_capture_quality": float(avg_quality),
            "capture_quality_attention": int(quality_review_count),
            "capture_quality_engine": quality_runtime_status(),
            "disease_distribution": [{"label": label, "count": count} for label, count in disease_rows],
            "estate_activity": [{"label": label, "count": count} for label, count in estate_rows],
            "recent": [_prediction_dict(row) for row in recent],
            "model": model_status(),
        }


@app.get("/api/export/predictions.csv")
def export_predictions(request: Request) -> StreamingResponse:
    _require(request, {"owner", "admin", "reviewer", "viewer"})
    with SessionLocal() as db:
        rows = db.execute(select(Prediction).order_by(Prediction.created_at.desc())).scalars().all()
        for row in rows:
            _ = row.estate, row.division, row.field
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["scan_ref", "created_at", "estate", "division", "field", "predicted_class", "confidence", "capture_quality_score", "capture_quality_grade", "quality_engine", "quality_warnings", "review_recommended", "review_status", "reviewed_class", "model_version", "image_sha256", "notes"])
        for row in rows:
            writer.writerow([
                row.scan_ref,
                row.created_at.isoformat() if row.created_at else "",
                row.estate.name if row.estate else "",
                row.division.name if row.division else "",
                row.field.field_code if row.field else "",
                row.predicted_class,
                f"{row.confidence:.6f}",
                f"{row.quality_assessment.quality_score:.1f}" if row.quality_assessment else "",
                row.quality_assessment.grade if row.quality_assessment else "",
                row.quality_assessment.engine_version if row.quality_assessment else "",
                "; ".join(json.loads(row.quality_assessment.warnings_json or "[]")) if row.quality_assessment else "",
                row.review_recommended,
                row.review_status,
                row.reviewed_class or "",
                row.model_version,
                row.image_sha256,
                row.capture_notes or "",
            ])
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tea_disease_predictions.csv"})
