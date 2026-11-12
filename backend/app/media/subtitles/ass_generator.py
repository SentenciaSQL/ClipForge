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


def _opacity_to_ass_alpha(opacity: float) -> str:
    """ASS alpha is inverted: 00=opaque, FF=transparent."""
    opacity = max(0.0, min(1.0, float(opacity)))
    return f"{int(round((1.0 - opacity) * 255)):02X}"


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


def _margin_v(preset: dict[str, Any], play_res_y: int) -> int:
    position = str(preset.get("position") or "bottom")
    safe = str(preset.get("safe_area") or "none")
    custom = preset.get("custom_vertical")
    if position == "custom" and custom is not None:
        # custom_vertical 0=top, 1=bottom → MarginV from bottom for bottom-aligned,
        # from top for top-aligned; use distance from nearest edge.
        y = max(0.0, min(1.0, float(custom)))
        return max(20, int(round((1.0 - y) * play_res_y)))
    if position == "top":
        base = 80
    elif position == "center":
        base = int(play_res_y * 0.42)
    else:
        base = 120
    if safe in {"tiktok", "reels", "shorts"} and position == "bottom":
        base = max(base, int(play_res_y * 0.12))
    if safe in {"tiktok", "reels", "shorts"} and position == "top":
        base = max(base, int(play_res_y * 0.10))
    return base


def _effective_max_chars(
    preset: dict[str, Any],
    *,
    play_res_x: int,
    margin_h: int,
    font_size: int,
) -> int:
    """
    Cap characters per line so bold/large captions fit a vertical canvas.

    Prefer the configured max_chars_per_line, but never exceed a width estimate
    from PlayResX / font size (uppercase Hormozi-style fonts are wide).
    """
    configured = int(preset.get("max_chars_per_line") or 28)
    configured = max(8, min(80, configured))
    usable = max(120, int(play_res_x) - 2 * max(int(margin_h), 0))
    # Bold caps are wide (≈0.7× font size); keep slack for outlines/shadows.
    approx_char_w = max(10.0, float(font_size) * (0.70 if preset.get("uppercase") else 0.58))
    fitted = max(8, int(usable / approx_char_w))
    return min(configured, fitted)


def _group_words(
    words: list[dict[str, Any]],
    *,
    max_chars_per_line: int = 22,
    max_lines: int = 2,
) -> list[list[dict[str, Any]]]:
    """
    Chunk words into on-screen captions that fit max_lines × max_chars_per_line.

    Also breaks early on sentence punctuation so captions stay readable.
    """
    max_chars_per_line = max(8, int(max_chars_per_line))
    max_lines = max(1, min(4, int(max_lines)))
    budget = max_chars_per_line * max_lines

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_len = 0

    for word in words:
        token = str(word.get("word") or "").strip()
        if not token:
            continue
        add = len(token) + (1 if current else 0)
        # Soft cap: start a new caption when the character budget is exceeded
        # (always keep at least one word in the current group).
        if current and current_len + add > budget:
            groups.append(current)
            current = [word]
            current_len = len(token)
        else:
            current.append(word)
            current_len += add

        end_sentence = token.rstrip().endswith((".", "!", "?"))
        # Hard break on sentence end once we have a bit of content.
        if end_sentence and current_len >= max(8, max_chars_per_line // 2):
            groups.append(current)
            current = []
            current_len = 0

    if current:
        groups.append(current)
    return groups


def _wrap_formatted_words(
    formatted: list[tuple[str, int]],
    *,
    max_chars_per_line: int,
) -> str:
    """
    Join pre-formatted ASS word tokens with spaces / \\N line breaks.

    `formatted` is a list of (ass_fragment, visible_char_len).
    """
    max_chars_per_line = max(8, int(max_chars_per_line))
    lines: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for fragment, visible_len in formatted:
        add = visible_len + (1 if current else 0)
        if current and current_len + add > max_chars_per_line:
            lines.append(current)
            current = [fragment]
            current_len = visible_len
        else:
            current.append(fragment)
            current_len += add
    if current:
        lines.append(current)
    return r"\N".join(" ".join(parts) for parts in lines)


def _event_prefix(animation: str) -> str:
    """ASS override tags applied at the start of each dialogue line."""
    if animation == "fade":
        return r"{\fad(120,120)}"
    if animation == "pop":
        return r"{\fscx120\fscy120\t(0,160,\fscx100\fscy100)}"
    if animation == "scale":
        return r"{\fscx80\fscy80\t(0,200,\fscx100\fscy100)}"
    if animation == "punch":
        return r"{\fscx130\fscy130\t(0,120,\fscx100\fscy100)}"
    return ""


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
    primary_alpha = _opacity_to_ass_alpha(float(preset.get("opacity") if preset.get("opacity") is not None else 1.0))
    primary = _ass_color(str(preset.get("primary_color") or "#FFFFFF"), alpha=primary_alpha)
    highlight = _ass_color(str(preset.get("highlight_color") or "#FFE600"), alpha=primary_alpha)
    outline = _ass_color(str(preset.get("outline_color") or "#000000"))
    outline_width = int(preset.get("outline_width") or 3)
    shadow = int(preset.get("shadow") or 1)
    bold = -1 if preset.get("bold", True) else 0
    italic = -1 if preset.get("italic") else 0
    spacing = float(preset.get("letter_spacing") or 0.0)
    align = _alignment(str(preset.get("position") or "center"), str(preset.get("alignment") or "center"))
    word_highlight = bool(preset.get("word_highlight", True))
    animation = str(preset.get("animation_preset") or "word")
    margin_h = int(preset.get("margin_h") or 80)
    margin_v = _margin_v(preset, play_res_y)
    box_enabled = bool(preset.get("box_enabled"))
    border_style = 3 if box_enabled else 1
    box_alpha = _opacity_to_ass_alpha(float(preset.get("box_opacity") if preset.get("box_opacity") is not None else 0.55))
    back = _ass_color(str(preset.get("box_color") or "#000000"), alpha=box_alpha)
    max_lines = max(1, min(4, int(preset.get("max_lines") or 2)))
    max_chars = _effective_max_chars(
        preset,
        play_res_x=play_res_x,
        margin_h=margin_h,
        font_size=font_size,
    )

    # WrapStyle 0 = smart word wrap (fallback); we still insert explicit \\N breaks.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary},{highlight},{outline},{back},{bold},{italic},0,0,100,100,{spacing:.1f},0,{border_style},{outline_width},{shadow},{align},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    prefix = _event_prefix(animation)
    groups = _group_words(
        relative_words,
        max_chars_per_line=max_chars,
        max_lines=max_lines,
    )
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
                formatted: list[tuple[str, int]] = []
                for word in group:
                    token = str(word["word"])
                    text = _escape_ass_text(token)
                    if word is active:
                        fragment = f"{{\\c{highlight}\\b1}}{text}{{\\c{primary}\\b0}}"
                    else:
                        fragment = text
                    formatted.append((fragment, len(token)))
                line = prefix + _wrap_formatted_words(formatted, max_chars_per_line=max_chars)
                events.append(
                    f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{line}"
                )
        else:
            formatted = [
                (_escape_ass_text(str(w["word"])), len(str(w["word"]))) for w in group
            ]
            line = prefix + _wrap_formatted_words(formatted, max_chars_per_line=max_chars)
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
