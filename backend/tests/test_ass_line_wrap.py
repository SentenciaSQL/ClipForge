"""ASS captions must wrap — not overflow a single 9:16 line."""

from __future__ import annotations

import re

from app.media.subtitles.ass_generator import (
    _effective_max_chars,
    _group_words,
    _wrap_formatted_words,
    build_ass_for_clip,
)


def _dialogue_texts(doc: str) -> list[str]:
    texts: list[str] = []
    for line in doc.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        # Format: Dialogue: Layer, Start, End, Style, Name, ML, MR, MV, Effect, Text
        # Effect is empty → text follows the final ",,"
        texts.append(line.rsplit(",,", 1)[-1])
    return texts


def test_wrap_inserts_explicit_breaks() -> None:
    parts = [("DESPUÉS", 7), ("DE", 2), ("AHÍ", 3), ("SABES", 5), ("QUE", 3), ("QUIERES", 7)]
    wrapped = _wrap_formatted_words(parts, max_chars_per_line=18)
    assert r"\N" in wrapped
    for row in wrapped.split(r"\N"):
        assert len(row.replace(" ", "")) <= 18 or " " in row
        assert len(row) <= 20


def test_group_respects_character_budget() -> None:
    words = [
        {"word": "DESPUÉS", "start": 0.0, "end": 0.2},
        {"word": "DE", "start": 0.2, "end": 0.3},
        {"word": "AHÍ", "start": 0.3, "end": 0.5},
        {"word": "SABES", "start": 0.5, "end": 0.7},
        {"word": "QUE", "start": 0.7, "end": 0.9},
        {"word": "QUIERES", "start": 0.9, "end": 1.1},
        {"word": "HACER", "start": 1.1, "end": 1.3},
    ]
    groups = _group_words(words, max_chars_per_line=16, max_lines=2)
    assert len(groups) >= 2
    for group in groups:
        length = sum(len(str(w["word"])) for w in group) + max(0, len(group) - 1)
        assert length <= 16 * 2 + 2


def test_build_ass_wraps_uppercase_hormozi_style() -> None:
    words = [
        {"word": "después", "start": 0.0, "end": 0.3},
        {"word": "de", "start": 0.3, "end": 0.45},
        {"word": "ahí", "start": 0.45, "end": 0.7},
        {"word": "sabes", "start": 0.7, "end": 1.0},
        {"word": "que", "start": 1.0, "end": 1.2},
        {"word": "quieres", "start": 1.2, "end": 1.5},
        {"word": "hacer", "start": 1.5, "end": 1.8},
    ]
    preset = {
        "font_family": "Montserrat",
        "font_size": 72,
        "primary_color": "#FFFFFF",
        "highlight_color": "#FFE600",
        "outline_color": "#000000",
        "outline_width": 4,
        "shadow": 2,
        "position": "bottom",
        "alignment": "center",
        "word_highlight": True,
        "animation_preset": "punch",
        "uppercase": True,
        "bold": True,
        "max_chars_per_line": 28,
        "max_lines": 2,
        "margin_h": 40,
        "opacity": 1,
    }
    max_chars = _effective_max_chars(preset, play_res_x=1080, margin_h=40, font_size=72)
    assert max_chars <= 20
    doc = build_ass_for_clip(
        words,
        clip_start=0,
        clip_end=10,
        preset=preset,
        play_res_x=1080,
        play_res_y=1920,
    )
    assert "WrapStyle: 0" in doc
    texts = _dialogue_texts(doc)
    assert texts
    assert any(r"\N" in text for text in texts)
    for text in texts:
        visible = re.sub(r"\{[^}]*\}", "", text)
        for row in visible.split(r"\N"):
            assert len(row) <= max_chars + 2, row
