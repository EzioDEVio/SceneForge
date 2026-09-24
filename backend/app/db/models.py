"""SQLAlchemy ORM models — the persistent project/scene/asset/job domain.

Scope note: this is the M1 subset of the full domain model described in the
specification (section 8). ImageThread/Message, ProviderProfile and
UsageRecord tables are stubbed minimally (provider_profiles) or deferred to
M2, and are called out as such in docs/architecture.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), default="Untitled project")
    language: Mapped[str] = mapped_column(String(16), default="ar")
    aspect: Mapped[str] = mapped_column(String(8), default="16:9")
    fps: Mapped[int] = mapped_column(Integer, default=30)
    width: Mapped[int] = mapped_column(Integer, default=1920)
    height: Mapped[int] = mapped_column(Integer, default=1080)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    default_font_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_FONT.copy())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Scene.order_index"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    jobs: Mapped[list["RenderJob"]] = relationship(back_populates="project", cascade="all, delete-orphan")


DEFAULT_FONT = {
    "family": "Noto Naskh Arabic",
    "size": 44,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 2,
    "background": "none",       # none | box | gradient
    "position": "bottom",       # bottom | top | middle
    "captions_enabled": True,
    "typewriter": False,        # reveal captions character-by-character
}


class Scene(Base):
    """A "Part" in the UI. Maps 1:1 to the spec's Scene entity."""

    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255), default="")

    original_text: Mapped[str] = mapped_column(Text, default="")
    spoken_text: Mapped[str] = mapped_column(Text, default="")
    subtitle_text: Mapped[str] = mapped_column(Text, default="")
    source_refs_json: Mapped[list] = mapped_column(JSON, default=list)

    timing_mode: Mapped[str] = mapped_column(String(16), default="audio_driven")
    requested_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_ms: Mapped[int] = mapped_column(Integer, default=250)
    trail_ms: Mapped[int] = mapped_column(Integer, default=400)

    effect_preset: Mapped[str] = mapped_column(String(32), default="original")
    effect_intensity: Mapped[float] = mapped_column(Integer, default=100)  # 0-100
    transition_in_json: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"type": "cut", "duration_ms": 0}
    )
    font_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_FONT.copy())
    # Glitch parameters, adjustment sliders and imported-LUT reference:
    # {"glitch": {...}, "adjust": {...}, "lut": {"asset_id", "strength"}}
    look_json: Mapped[dict] = mapped_column(JSON, default=dict)

    revision: Mapped[int] = mapped_column(Integer, default=1)
    # Hash of the inputs that produced the current rendered part artifact.
    # Used to detect "stale" parts without regenerating anything eagerly.
    rendered_plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rendered_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", use_alter=True, name="fk_scene_rendered_asset"), nullable=True
    )
    measured_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="scenes")
    shots: Mapped[list["Shot"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan", order_by="Shot.order_index",
        foreign_keys="Shot.scene_id",
    )
    voice_takes: Mapped[list["VoiceTake"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan", order_by="VoiceTake.created_at",
        foreign_keys="VoiceTake.scene_id",
    )


class Asset(Base):
    """A content-addressed media blob (uploaded, generated, or rendered)."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    type: Mapped[str] = mapped_column(String(16))  # image|video|audio
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))  # relative path under MEDIA_DIR/RENDERS_DIR
    mime: Mapped[str] = mapped_column(String(64), default="")
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str] = mapped_column(String(32), default="upload")
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    creator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped["Project"] = relationship(back_populates="assets")


class Shot(Base):
    """One visual element within a scene (image or video clip + motion)."""

    __tablename__ = "shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    is_selected: Mapped[bool] = mapped_column(Boolean, default=True)

    source_in_ms: Mapped[int] = mapped_column(Integer, default=0)
    source_out_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = proportional share

    fit: Mapped[str] = mapped_column(String(16), default="cover")
    crop_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    motion_json: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"type": "static", "start": {"x": 0.5, "y": 0.5, "scale": 1.0},
                                "end": {"x": 0.5, "y": 0.5, "scale": 1.0}}
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    scene: Mapped["Scene"] = relationship(back_populates="shots", foreign_keys=[scene_id])
    asset: Mapped["Asset"] = relationship(foreign_keys=[asset_id])


class VoiceTake(Base):
    __tablename__ = "voice_takes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"))
    spoken_text_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="upload")  # VoiceTakeSource
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audio_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    measured_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Non-destructive trim/volume/fade (render/audio_edit.py).
    edit_json: Mapped[dict] = mapped_column(JSON, default=dict)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    scene: Mapped["Scene"] = relationship(back_populates="voice_takes", foreign_keys=[scene_id])
    audio_asset: Mapped["Asset"] = relationship(foreign_keys=[audio_asset_id])


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(16))  # part|full_export|preview
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[float] = mapped_column(Integer, default=0)  # 0-100
    plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    events_json: Mapped[list] = mapped_column(JSON, default=list)  # append-only progress log for SSE replay
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="jobs")


class ProviderProfile(Base):
    """Stub for M2+. Secrets are never stored in plaintext columns here —
    only a reference key into the OS credential vault (backend/app/security).
    """

    __tablename__ = "provider_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    capability: Mapped[str] = mapped_column(String(32))  # image|speech|text|media_search|transcription
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    capabilities_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
