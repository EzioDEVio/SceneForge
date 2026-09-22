"""TXT/Markdown script import parser (spec section 9).

Detects common documentary-script headings in Arabic and English and
splits into scene-shaped records with distinct original/spoken/subtitle
text and preserved citation markers. Never silently drops unmatched text:
anything that doesn't match a recognized heading is kept in a scene's
original_text (recoverable) with a warning, rather than discarded.
"""
from __future__ import annotations

import re

HEADING_PATTERNS = [
    re.compile(r"^\s*(?:اللقطة|المشهد)\s*[\d٠-٩]+", re.UNICODE),
    re.compile(r"^\s*Scene\s*\d+", re.IGNORECASE),
]
FIELD_PATTERNS = {
    "visual": re.compile(r"^\s*(?:Visual|AI Image Prompt|الصورة|اللقطة البصرية)\s*[:：]\s*(.*)$", re.IGNORECASE | re.UNICODE),
    "on_screen": re.compile(r"^\s*(?:On[- ]?Screen Text|النص على الشاشة)\s*[:：]\s*(.*)$", re.IGNORECASE | re.UNICODE),
    "narration": re.compile(r"^\s*(?:Arabic Voice Narrative|Narration|السرد|التعليق الصوتي)\s*[:：]\s*(.*)$", re.IGNORECASE | re.UNICODE),
    "timecode": re.compile(r"^\s*(?:Timecode|التوقيت)\s*[:：]\s*(.*)$", re.IGNORECASE | re.UNICODE),
}
CITATION_PATTERN = re.compile(r"\[\d+(?:,\s*\d+)*\]")


def _split_into_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if any(p.match(line) for p in HEADING_PATTERNS):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks]


def parse_script(text: str) -> dict:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return {"scenes": [], "unclassified_text": None, "warnings": ["Empty input."]}

    blocks = _split_into_blocks(text)
    scenes = []
    warnings: list[str] = []
    unclassified: list[str] = []

    if len(blocks) == 1 and not any(p.match(blocks[0].splitlines()[0]) for p in HEADING_PATTERNS):
        # No recognizable headings at all — treat the whole thing as a
        # single recoverable block rather than silently dropping text.
        unclassified.append(blocks[0])
        warnings.append(
            "No scene headings (e.g. 'Scene 1' / 'اللقطة 1') were detected. "
            "The full text was preserved as one scene's original text — split it manually."
        )
        scenes.append({
            "title": "Imported text",
            "original_text": blocks[0].strip(),
            "spoken_text": _strip_non_narration(blocks[0]),
            "subtitle_text": _strip_citations(_strip_non_narration(blocks[0])),
            "source_refs": _extract_refs(blocks[0]),
            "warnings": ["No template match; review before generating."],
            "matched_template": False,
        })
        return {"scenes": scenes, "unclassified_text": None, "warnings": warnings}

    for block in blocks:
        lines = block.splitlines()
        heading = lines[0].strip() if lines else ""
        body_lines = lines[1:]

        fields = {"visual": [], "on_screen": [], "narration": [], "timecode": [], "other": []}
        for line in body_lines:
            matched = False
            for key, pattern in FIELD_PATTERNS.items():
                m = pattern.match(line)
                if m:
                    fields[key].append(m.group(1))
                    matched = True
                    break
            if not matched and line.strip():
                fields["other"].append(line)

        narration_text = "\n".join(fields["narration"]).strip()
        visual_text = "\n".join(fields["visual"]).strip()
        other_text = "\n".join(fields["other"]).strip()
        matched_template = bool(narration_text or visual_text or fields["on_screen"] or fields["timecode"])

        original_parts = []
        if visual_text:
            original_parts.append(f"[Visual] {visual_text}")
        if fields["on_screen"]:
            original_parts.append(f"[On-screen] {' '.join(fields['on_screen'])}")
        if fields["timecode"]:
            original_parts.append(f"[Timecode] {' '.join(fields['timecode'])} (suggestion only)")
        if narration_text:
            original_parts.append(narration_text)
        if other_text:
            original_parts.append(other_text)
        original_text = "\n".join(original_parts).strip() or block.strip()

        spoken_source = narration_text or (other_text if not matched_template else "")
        spoken_text = _strip_non_narration(spoken_source)
        subtitle_text = _strip_citations(spoken_text)

        scene_warnings = []
        if not matched_template:
            scene_warnings.append("Heading found but no recognized fields; full block kept as original_text for manual repair.")
        if not narration_text and not other_text:
            scene_warnings.append("No narration text detected for this scene.")

        scenes.append({
            "title": heading or f"Scene {len(scenes) + 1}",
            "original_text": original_text,
            "spoken_text": spoken_text,
            "subtitle_text": subtitle_text,
            "source_refs": _extract_refs(block),
            "warnings": scene_warnings,
            "matched_template": matched_template,
        })

    return {"scenes": scenes, "unclassified_text": None, "warnings": warnings}


def _strip_non_narration(text: str) -> str:
    """Narration must not read image prompts, timestamps, stage directions
    or headings aloud (spec section 6). This trims common stage-direction
    bracket notations like (pause) / [music] left over in narration text."""
    text = re.sub(r"\((?:pause|beat|music|sfx)[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[(?:music|sfx)[^\]]*\]", "", text, flags=re.IGNORECASE)
    return text.strip()


def _strip_citations(text: str) -> str:
    return CITATION_PATTERN.sub("", text).strip()


def _extract_refs(text: str) -> list[str]:
    return CITATION_PATTERN.findall(text)
