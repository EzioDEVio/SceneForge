"""One explicit failure for unavailable Pillow/FreeType; never silently replace text."""
from pathlib import Path

class FontRuntimeError(RuntimeError):
    pass


def load_font(path, size, **kwargs):
    from PIL import ImageFont
    # An open file also avoids FreeType's narrow Windows filename handling.
    import io
    try:
        data = Path(path).read_bytes()
        return ImageFont.truetype(io.BytesIO(data), size, **kwargs)
    except (ImportError, OSError) as exc:
        raise FontRuntimeError(
            'Text rendering is unavailable because Pillow could not load its font runtime or bundled font. '
            'Close SceneForge, run scripts/setup.bat (or scripts/setup.ps1), then restart with scripts/start.bat. '
            'Setup installs a fresh runtime outside the long project path. Your project data stays in place. '
            'If setup still fails, extract the app to a short path such as C:\\SceneForge and rerun setup.'
        ) from exc


def check_font_runtime():
    from app.config import RESOURCE_DIR
    from PIL import Image, ImageDraw
    from app.render.textured_text import _shape
    for name, text in [('NotoSans-Bold.ttf', 'SceneForge'), ('NotoNaskhArabic-Bold.ttf', 'مرحبا')]:
        font = load_font(Path(RESOURCE_DIR) / 'assets/fonts' / name, 32)
        image = Image.new('L', (320, 100))
        ImageDraw.Draw(image).text((10, 10), _shape(text), font=font, fill=255)
        if image.getbbox() is None:
            raise FontRuntimeError('The font runtime produced an empty image. Rerun scripts/setup.bat.')
