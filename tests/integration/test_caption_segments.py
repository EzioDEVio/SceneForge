"""Focused rendering smoke test for individually timed auto-caption clips."""
from pathlib import Path
from tempfile import TemporaryDirectory

from app.render.subtitles import write_ass_file


def main():
    with TemporaryDirectory(prefix="sf-caption-segments-") as temp:
        path = Path(temp) / "captions.ass"
        write_ass_file(
            "scene", "hello from today", 1400,
            {
                "captions_enabled": True,
                "split": "phrases",
                "phrase_words": 2,
                "caption_segments": [
                    {"id": "a", "text": "hello from", "start_ms": 0, "end_ms": 600},
                    {"id": "b", "text": "today", "start_ms": 700, "end_ms": 1200},
                ],
                "transcript": {"words": [["hello", 0, 250], ["from", 300, 550], ["today", 700, 1100]]},
                "karaoke": True,
                "karaoke_style": "color",
                "highlight_color": "#FFD84D",
                "caption_direction": "rtl",
            }, 1280, 720, str(path),
        )
        dialogue = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
        # Karaoke creates one event per spoken word, but all events retain the
        # timing bounds of their editable caption clip.
        assert any("hello" in line and ",0:00:00.00,0:00:00.30," in line for line in dialogue)
        assert any("from" in line and ",0:00:00.30,0:00:00.60," in line for line in dialogue)
        assert any("today" in line and ",0:00:00.70,0:00:01.20," in line for line in dialogue)
        assert any("\u200f" in line for line in dialogue), "RTL mark should guide Arabic/Latin bidi layout"
        assert all("hello from today" not in line for line in dialogue)
        write_ass_file(
            "scene", "Hello مرحبا", 1000,
            {"captions_enabled": True, "caption_direction": "ltr"},
            1280, 720, str(path),
        )
        ltr_dialogue = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
        assert any("\u200e" in line for line in ltr_dialogue), "LTR mark should guide mixed-script layout"
        print("PASS independently timed caption clips render as separate ASS dialogue cues")
        print("PASS explicit RTL and LTR directions are embedded for mixed-script captions")


if __name__ == "__main__":
    main()
