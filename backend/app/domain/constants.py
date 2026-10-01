"""Enumerations shared by the domain, API and renderer layers.

Kept as plain str-Enums (not free-form strings) so unsupported combinations
are rejected by validation instead of failing late inside FFmpeg.
"""
from __future__ import annotations

from enum import Enum


class AspectRatio(str, Enum):
    WIDE_16_9 = "16:9"
    TALL_9_16 = "9:16"
    SQUARE_1_1 = "1:1"


ASPECT_DIMENSIONS = {
    AspectRatio.WIDE_16_9: (1920, 1080),
    AspectRatio.TALL_9_16: (1080, 1920),
    AspectRatio.SQUARE_1_1: (1080, 1080),
}
PREVIEW_ASPECT_DIMENSIONS = {
    AspectRatio.WIDE_16_9: (1280, 720),
    AspectRatio.TALL_9_16: (720, 1280),
    AspectRatio.SQUARE_1_1: (720, 720),
}


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    LUT = "lut"          # imported .cube colour LUT (never on the timeline)


class AssetOrigin(str, Enum):
    UPLOAD = "upload"
    GENERATED = "generated"       # AI image/video generation (M2+)
    STOCK_SEARCH = "stock_search"  # Pexels/Pixabay (M3)
    LOCAL_TTS = "local_tts"       # offline espeak-ng narration (M1 fixture path)
    RENDER_OUTPUT = "render_output"


class FitMode(str, Enum):
    COVER = "cover"                # crop to fill
    CONTAIN = "contain"            # letterbox, solid background
    CONTAIN_BLUR = "contain_blur"  # letterbox, blurred background fill


class MotionType(str, Enum):
    STATIC = "static"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    CLOSE_UP = "close_up"
    DIAGONAL_UP = "diagonal_up"
    DIAGONAL_DOWN = "diagonal_down"
    PUSH_LEFT = "push_left"
    PULL_RIGHT = "pull_right"
    KEN_BURNS = "ken_burns"         # explicit start/end focal point + scale


class EffectPreset(str, Enum):
    ORIGINAL = "original"
    BLACK_AND_WHITE = "black_and_white"
    SEPIA = "sepia"
    WARM = "warm"
    COOL = "cool"
    VINTAGE = "vintage"
    VIGNETTE = "vignette"
    SOFT_GLOW = "soft_glow"
    GLITCH = "glitch"
    OLD_FILM = "old_film"
    TEAL_AMBER = "teal_amber"
    PASTEL = "pastel"
    BLEACH_BYPASS = "bleach_bypass"
    VHS = "vhs"
    GLOW = "glow"
    DUOTONE = "duotone"
    NEWSPRINT = "newsprint"
    FILM_GRAIN = "film_grain"
    HIGH_CONTRAST = "high_contrast"
    FADED = "faded"
    DREAM = "dream"
    CINEMATIC = "cinematic"
    NOIR = "noir"
    SHARPEN = "sharpen"
    NEGATIVE = "negative"
    GOLDEN_HOUR = "golden_hour"
    ARCTIC = "arctic"
    PORTRA = "portra"
    MATTE = "matte"
    POP_COLOR = "pop_color"
    TEAL_SHADOW = "teal_shadow"
    ROSE_GLOW = "rose_glow"
    MONO_BLUE = "mono_blue"
    CHROMATIC_SPLIT = "chromatic_split"
    MOTION_TRAIL = "motion_trail"
    # rc6 effects pack (FFmpeg filters, not AI)
    FOCUS_BLUR = "focus_blur"
    TILT_SHIFT = "tilt_shift"
    MOSAIC = "mosaic"
    HALATION = "halation"
    PRINT_2383 = "print_2383"
    TUNGSTEN_NIGHT = "tungsten_night"
    CROSS_PROCESS = "cross_process"


class TransitionType(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_THROUGH_BLACK = "fade_through_black"
    SLIDE = "slide"
    SLIDE_RIGHT = "slide_right"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    FADE_WHITE = "fade_white"
    CIRCLE_OPEN = "circle_open"
    CIRCLE_CLOSE = "circle_close"
    ZOOM_IN = "zoom_in"
    SMOOTH_LEFT = "smooth_left"
    SMOOTH_RIGHT = "smooth_right"
    RADIAL = "radial"
    PIXELIZE = "pixelize"
    BLUR = "blur"
    DIAGONAL = "diagonal"
    SQUEEZE = "squeeze"
    FADE_GRAYS = "fade_grays"
    FILM_BURN = "film_burn"
    WIND = "wind"
    SLICE = "slice"
    OPEN = "open"
    CLOSE = "close"
    FADE_FAST = "fade_fast"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    SMOOTH_UP = "smooth_up"
    SMOOTH_DOWN = "smooth_down"
    WIPE_UP = "wipe_up"
    WIPE_DOWN = "wipe_down"
    COVER_LEFT = "cover_left"
    COVER_RIGHT = "cover_right"
    REVEAL_LEFT = "reveal_left"
    REVEAL_RIGHT = "reveal_right"
    VERT_OPEN = "vert_open"
    VERT_CLOSE = "vert_close"
    DIAGONAL_TR = "diagonal_tr"
    RECT_CROP = "rect_crop"
    DISTANCE = "distance"
    SLICE_VERTICAL = "slice_vertical"
    WIND_UP = "wind_up"
    SQUEEZE_V = "squeeze_v"
    COVER_UP = "cover_up"
    COVER_DOWN = "cover_down"
    REVEAL_UP = "reveal_up"
    REVEAL_DOWN = "reveal_down"
    WIPE_TL = "wipe_tl"
    WIPE_TR = "wipe_tr"
    WIPE_BL = "wipe_bl"
    WIPE_BR = "wipe_br"
    SLICE_HORIZONTAL = "slice_horizontal"
    WIND_RIGHT = "wind_right"
    WIND_DOWN = "wind_down"
    FADE_SLOW = "fade_slow"


class TimingMode(str, Enum):
    AUDIO_DRIVEN = "audio_driven"   # duration = measured narration + lead/trail
    FIXED = "fixed"                 # explicit requested_duration_ms


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class JobScope(str, Enum):
    PART = "part"           # render a single scene/part
    FULL_EXPORT = "full_export"
    PREVIEW = "preview"


class VoiceTakeSource(str, Enum):
    UPLOAD = "upload"
    LOCAL_OFFLINE_TTS = "local_offline_tts"   # espeak-ng, no-key, experimental
    CLOUD_TTS = "cloud_tts"                   # M2+, requires provider profile
    MUTED = "muted"


CAPTION_POSITIONS = ("bottom", "top", "middle")
