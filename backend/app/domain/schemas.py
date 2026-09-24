from __future__ import annotations

from typing import Any

from pydantic import model_validator, BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = "Untitled project"
    language: str = "ar"
    aspect: str = "16:9"


class ProjectOut(BaseModel):
    id: str
    title: str
    language: str
    aspect: str
    fps: int
    width: int
    height: int
    revision: int
    default_font_json: dict
    finishing_json: dict = {}

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    title: str | None = None
    aspect: str | None = None
    language: str | None = None
    finishing: dict | None = None


class AssetOut(BaseModel):
    id: str
    type: str
    mime: str
    original_filename: str
    width: int | None
    height: int | None
    duration_ms: int | None
    origin: str
    source_url: str | None = None
    creator: str | None = None
    license_note: str | None = None

    class Config:
        from_attributes = True


class ShotIn(BaseModel):
    asset_id: str
    order_index: int = 0
    fit: str = "cover"
    motion: dict = Field(default_factory=lambda: {"type": "static"})
    source_in_ms: int = 0
    source_out_ms: int | None = None
    duration_ms: int | None = None
    crop: dict | None = None


class ShotOut(BaseModel):
    crop_json: dict | None = None
    id: str
    asset_id: str
    order_index: int
    fit: str
    motion_json: dict
    source_in_ms: int
    source_out_ms: int | None
    duration_ms: int | None
    is_selected: bool
    asset: AssetOut | None = None

    class Config:
        from_attributes = True


class VoiceTakeOut(BaseModel):
    id: str
    source: str
    provider: str | None
    voice: str | None
    measured_duration_ms: int | None
    accepted: bool
    stale: bool
    audio_asset: AssetOut | None = None
    edit_json: dict = {}
    # Length after trimming; this is what "Match narration" uses.
    effective_duration_ms: int | None = None

    @model_validator(mode="after")
    def _effective(self):
        from app.render.audio_edit import effective_ms
        self.effective_duration_ms = effective_ms(self.measured_duration_ms, self.edit_json)
        return self

    class Config:
        from_attributes = True


class SceneCreate(BaseModel):
    title: str = ""
    original_text: str = ""


class SceneUpdate(BaseModel):
    title: str | None = None
    original_text: str | None = None
    spoken_text: str | None = None
    subtitle_text: str | None = None
    effect_preset: str | None = None
    effect_intensity: int | None = None
    transition_in: dict | None = None
    font: dict | None = None
    look: dict | None = None
    lead_ms: int | None = None
    trail_ms: int | None = None
    requested_duration_ms: int | None = None
    timing_mode: str | None = None


class SceneOut(BaseModel):
    id: str
    project_id: str
    order_index: int
    title: str
    original_text: str
    spoken_text: str
    subtitle_text: str
    timing_mode: str
    requested_duration_ms: int | None
    lead_ms: int
    trail_ms: int
    effect_preset: str
    effect_intensity: int
    transition_in_json: dict
    font_json: dict
    look_json: dict = {}
    revision: int
    rendered_plan_hash: str | None
    rendered_asset_id: str | None
    measured_duration_ms: int | None
    shots: list[ShotOut] = []
    voice_takes: list[VoiceTakeOut] = []
    is_stale: bool = False

    class Config:
        from_attributes = True


class ReorderRequest(BaseModel):
    scene_ids: list[str]


class ImportPreviewRequest(BaseModel):
    text: str
    filename: str | None = None


class ImportPreviewScene(BaseModel):
    title: str
    original_text: str
    spoken_text: str
    subtitle_text: str
    source_refs: list[str]
    warnings: list[str] = []
    matched_template: bool = False


class ImportPreviewResponse(BaseModel):
    scenes: list[ImportPreviewScene]
    unclassified_text: str | None = None
    warnings: list[str] = []


class ImportApplyRequest(BaseModel):
    scenes: list[ImportPreviewScene]
    replace_existing: bool = False


class VoiceTakeCreate(BaseModel):
    source: str  # 'local_offline_tts' | 'upload' handled by separate endpoints
    voice: str | None = "ar"
    rate_wpm: int | None = None


class VoiceTakeSelect(BaseModel):
    take_id: str


class JobOut(BaseModel):
    id: str
    project_id: str
    scene_id: str | None
    scope: str
    status: str
    stage: str
    progress: int
    error: str | None
    artifact_asset_id: str | None

    class Config:
        from_attributes = True


class JobCreateResponse(BaseModel):
    job_id: str


class ProviderProfileCreate(BaseModel):
    capability: str  # "image" | "speech" | ...
    name: str        # "openai" for now
    api_key: str
    model: str | None = None
    base_url: str | None = None


class ProviderProfileOut(BaseModel):
    id: str
    capability: str
    name: str
    model: str | None
    base_url: str | None
    masked_key: str
    configured: bool = True

    class Config:
        from_attributes = True


class LocalImageOptions(BaseModel):
    family: str = Field(default="sd15", pattern=r"^(sd15|sdxl)$")
    steps: int = Field(default=30, ge=10, le=60)
    cfg_scale: float = Field(default=7, ge=1, le=15)
    seed: int = Field(default=-1, ge=-1, le=4294967295)
    negative_prompt: str = Field(default="", max_length=3000)
    hires: bool = False


class GenerateImageRequest(BaseModel):
    local_options: LocalImageOptions | None = None
    prompt: str = Field(min_length=1, max_length=10000)
    size: str = Field(default="1024x1024", pattern=r"^(1024x1024|1536x1024|1024x1536)$")
    provider_id: str | None = None


class TextLayer(BaseModel):
    family: str = Field(default="Noto Naskh Arabic", pattern=r"^(Noto Naskh Arabic|Noto Sans Arabic|Noto Sans)$")
    align: str = Field(default="center", pattern=r"^(left|center|right)$")
    outline_width: float = Field(default=0, ge=0, le=10)
    shadow: float = Field(default=0, ge=0, le=10)
    exit_ms: int = Field(default=0, ge=0, le=10000)
    animation: str = Field(default="none", pattern=r"^(none|fade|slide|slide-right|slide-up|slide-down|zoom|reveal|typewriter|blur|glitch)$")
    animation_ms: int = Field(default=800, ge=100, le=10000)
    id: str = Field(max_length=80)
    text: str = Field(max_length=2000)
    x: float = Field(default=50, ge=0, le=100)
    y: float = Field(default=50, ge=0, le=100)
    size: int = Field(default=64, ge=12, le=200)
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    start_ms: int = Field(default=0, ge=0, le=3600000)
    end_ms: int = Field(default=0, ge=0, le=3600000)
    bold: bool = False
