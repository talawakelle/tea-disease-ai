from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine_kwargs = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30), default="operator")
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionToken(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class Estate(Base):
    __tablename__ = "estates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Division(Base):
    __tablename__ = "divisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    estate: Mapped[Estate] = relationship()


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id", ondelete="CASCADE"), index=True)
    field_code: Mapped[str] = mapped_column(String(100), index=True)
    hectares: Mapped[float | None] = mapped_column(Float, nullable=True)
    clone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    division: Mapped[Division] = relationship()


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_ref: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    estate_id: Mapped[int | None] = mapped_column(ForeignKey("estates.id"), nullable=True, index=True)
    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True, index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), nullable=True, index=True)
    image_path: Mapped[str] = mapped_column(Text)
    image_sha256: Mapped[str] = mapped_column(String(64), index=True)
    predicted_class: Mapped[str] = mapped_column(String(100), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    second_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    second_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    top3_json: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(150), index=True)
    model_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed", index=True)
    reviewed_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    estate: Mapped[Estate | None] = relationship()
    division: Mapped[Division | None] = relationship()
    field: Mapped[Field | None] = relationship()
    quality_assessment: Mapped["QualityAssessment | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )


class QualityAssessment(Base):
    __tablename__ = "quality_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"), unique=True, index=True)
    engine_version: Mapped[str] = mapped_column(String(100), index=True)
    original_path: Mapped[str] = mapped_column(Text)
    processed_path: Mapped[str] = mapped_column(Text)
    original_width: Mapped[int] = mapped_column(Integer)
    original_height: Mapped[int] = mapped_column(Integer)
    processed_width: Mapped[int] = mapped_column(Integer)
    processed_height: Mapped[int] = mapped_column(Integer)
    quality_score: Mapped[float] = mapped_column(Float, index=True)
    grade: Mapped[str] = mapped_column(String(30), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    hard_fail_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    blur_variance: Mapped[float] = mapped_column(Float)
    brightness_mean: Mapped[float] = mapped_column(Float)
    dark_ratio: Mapped[float] = mapped_column(Float)
    bright_ratio: Mapped[float] = mapped_column(Float)
    contrast_std: Mapped[float] = mapped_column(Float)
    saturation_mean: Mapped[float] = mapped_column(Float)
    leaf_like_coverage: Mapped[float] = mapped_column(Float)
    center_leaf_like_coverage: Mapped[float] = mapped_column(Float)
    preprocessing_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    prediction: Mapped[Prediction] = relationship(back_populates="quality_assessment")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
