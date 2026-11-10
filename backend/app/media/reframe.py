"""Vertical reframing helpers for 9:16 short-form exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ReframeMode = Literal[
    "auto",
    "smart_crop",
    "center_crop",
    "blurred_bg",
    "podcast",
    "gaming",
    "tutorial",
    "educational",
    "general",
]


@dataclass
class ReframePlan:
    mode: str
    filter_chain: str
    face_x_ratio: float | None = None
    notes: str = ""


def _resolve_mode(mode: str, *, has_faces: bool) -> str:
    normalized = (mode or "auto").lower()
    if normalized in {"auto", "general"}:
        return "smart_crop" if has_faces else "center_crop"
    if normalized == "podcast":
        return "smart_crop" if has_faces else "center_crop"
    if normalized in {"gaming", "tutorial", "educational"}:
        # Prefer keeping the full frame composition with blurred sides.
        return "blurred_bg"
    if normalized in {"smart_crop", "center_crop", "blurred_bg"}:
        return normalized
    return "center_crop"


def detect_subject_x_ratio(
    video_path: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    sample_count: int = 8,
) -> float | None:
    """Estimate horizontal subject position using OpenCV Haar face detection."""
    try:
        import cv2  # type: ignore
    except Exception:
        logger.warning("OpenCV unavailable; smart crop will fall back to center")
        return None

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 1.0
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        capture.release()
        return None

    centers: list[float] = []
    for index in range(sample_count):
        t = start_seconds + (duration_seconds * (index + 0.5) / sample_count)
        frame_idx = max(int(t * fps), 0)
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
        if len(faces) == 0:
            continue
        # Largest face
        x, _y, w, _h = max(faces, key=lambda item: item[2] * item[3])
        centers.append((x + w / 2.0) / float(width))

    capture.release()
    if not centers:
        return None
    return sum(centers) / len(centers)


def build_reframe_filter(
    *,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
    mode: str,
    face_x_ratio: float | None = None,
) -> ReframePlan:
    target_mode = _resolve_mode(mode, has_faces=face_x_ratio is not None)
    out_w, out_h = output_width, output_height

    if target_mode == "blurred_bg":
        # Fit source inside 9:16, blur-fill the remaining canvas.
        chain = (
            f"split[original][bg];"
            f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=20:5[blurred];"
            f"[original]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease[fg];"
            f"[blurred][fg]overlay=(W-w)/2:(H-h)/2"
        )
        return ReframePlan(mode=target_mode, filter_chain=chain, face_x_ratio=face_x_ratio, notes="blurred background")

    # Crop to vertical then scale.
    src_w = max(source_width, 1)
    src_h = max(source_height, 1)
    target_aspect = out_w / out_h
    crop_h = src_h
    crop_w = int(round(crop_h * target_aspect))
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(round(crop_w / target_aspect))

    if target_mode == "smart_crop" and face_x_ratio is not None:
        center_x = face_x_ratio * src_w
        x = int(round(center_x - crop_w / 2))
        x = max(0, min(x, src_w - crop_w))
        note = f"smart crop around x_ratio={face_x_ratio:.3f}"
    else:
        x = max(0, (src_w - crop_w) // 2)
        note = "center crop"

    y = max(0, (src_h - crop_h) // 2)
    chain = f"crop={crop_w}:{crop_h}:{x}:{y},scale={out_w}:{out_h}"
    return ReframePlan(mode=target_mode, filter_chain=chain, face_x_ratio=face_x_ratio, notes=note)


def plan_reframe_for_clip(
    video_path: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    source_width: int | None,
    source_height: int | None,
    output_width: int,
    output_height: int,
    mode: str,
) -> ReframePlan:
    face_ratio = None
    resolved = (mode or "auto").lower()
    if resolved in {"auto", "smart_crop", "podcast", "general"}:
        face_ratio = detect_subject_x_ratio(
            video_path,
            start_seconds=start_seconds,
            duration_seconds=duration_seconds,
        )
    return build_reframe_filter(
        source_width=int(source_width or 1920),
        source_height=int(source_height or 1080),
        output_width=output_width,
        output_height=output_height,
        mode=mode,
        face_x_ratio=face_ratio,
    )
