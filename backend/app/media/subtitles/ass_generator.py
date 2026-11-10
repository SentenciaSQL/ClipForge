"""Generate ASS subtitle files with word-level highlighting for clip timelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _ass_color(hex_color: str, alpha: str = "00") -> str:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha}{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def _alignment(position: str, alignment: str) -> int:
    # ASS numpad alignments
    if position == "top":
        return 8 if alignment == "center" else (7 if alignment == "left" else 9)
    if position == "center":
        return 5 if alignment == "center" else (4 if alignment == "left" else 6)
    return 2 if alignment == "center" else (1 if alignment == "left" else 3)


def _group_words(
    words: list[dict[str, Any]],
    *,
    max_words: int = 4,
) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        current.append(word)
        token = str(word.get("word") or "")
        end_sentence = token.rstrip().endswith((".", "!", "?", ",", ";"))
        if len(current) >= max_words or end_sentence:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def build_ass_for_clip(
    words: list[dict[str, Any]],
    *,
    clip_start: float,
    clip_end: float,
    preset: dict[str, Any],
    play_res_x: int = 1080,
    play_res_y: int = 1920,
) -> str:
    """
    Build an ASS document with timestamps relative to the clip timeline.

    Absolute transcription times are shifted by subtracting clip_start.
    """
    relative_words: list[dict[str, Any]] = []
    for word in words:
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        if end <= clip_start or start >= clip_end:
            continue
        rel_start = max(0.0, start - clip_start)
        rel_end = max(rel_start + 0.04, min(clip_end, end) - clip_start)
        token = str(word.get("word") or "").strip()
        if not token:
            continue
        if preset.get("uppercase"):
            token = token.upper()
        relative_words.append({"word": token, "start": rel_start, "end": rel_end})

    font = str(preset.get("font_family") or "DejaVu Sans")
    font_size = int(preset.get("font_size") or 64)
    primary = _ass_color(str(preset.get("primary_color") or "#FFFFFF"))
    highlight = _ass_color(str(preset.get("highlight_color") or "#FFE600"))
    outline = _ass_color(str(preset.get("outline_color") or "#000000"))
    outline_width = int(preset.get("outline_width") or 3)
    shadow = int(preset.get("shadow") or 1)
    bold = -1 if preset.get("bold", True) else 0
    align = _alignment(str(preset.get("position") or "center"), str(preset.get("alignment") or "center"))
    word_highlight = bool(preset.get("word_highlight", True))
    margin_v = 120 if str(preset.get("position") or "center") == "bottom" else 80

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary},{highlight},{outline},&H80000000,{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow},{align},80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    groups = _group_words(relative_words, max_words=int(preset.get("max_lines", 2)) * 3 or 4)
    for group in groups:
        if not group:
            continue
        group_start = group[0]["start"]
        group_end = group[-1]["end"]
        if word_highlight:
            for index, active in enumerate(group):
                # Show the phrase while the active word is spoken.
                start = active["start"]
                end = group[index + 1]["start"] if index + 1 < len(group) else group_end
                parts: list[str] = []
                for word in group:
                    text = _escape_ass_text(str(word["word"]))
                    if word is active:
                        parts.append(f"{{\\c{highlight}\\b1}}{text}{{\\c{primary}\\b0}}")
                    else:
                        parts.append(text)
                line = " ".join(parts)
                events.append(
                    f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{line}"
                )
        else:
            line = " ".join(_escape_ass_text(str(w["word"])) for w in group)
            events.append(
                f"Dialogue: 0,{_ass_time(group_start)},{_ass_time(group_end)},Default,,0,0,0,,{line}"
            )

    if not events:
        # Fallback single event from empty words — keep valid ASS.
        events.append("Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,")

    return header + "\n".join(events) + "\n"


def write_ass_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
