"""Vertical / multi-aspect reframing helpers for short-form exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.logging import get_logger
from app.media.source_quality import analyze_crop_impact, recommend_reframe_mode

logger = get_logger(__name__)

ReframeMode = Literal[
    "auto",
    "smart_crop",
    "center_crop",
    "blurred_bg",
    "solid_bg",
    "original",
    "fit_original",
    "manual",
    "podcast",
    "gaming",
    "tutorial",
    "educational",
    "general",
]

# High-quality scaler for any necessary resize (never stretch with different SAR casually).
_SCALE_FLAGS = "flags=lanczos+accurate_rnd+full_chroma_int"


@dataclass
class ReframePlan:
    mode: str
    filter_chain: str
    face_x_ratio: float | None = None
    notes: str = ""
    effective_crop_width: int | None = None
    effective_crop_height: int | None = None
    linear_upscale: float | None = None


def _resolve_mode(
    mode: str,
    *,
    has_faces: bool,
    enable_face_detection: bool,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
) -> str:
    normalized = (mode or "auto").lower()
    if normalized == "fit_original":
        return "original"
    if normalized in {"auto", "general"}:
        # Quality-aware: avoid destructive vertical crops on landscape / low-res sources.
        aspect_key = "9:16"
        if output_width and output_height:
            ratio = output_width / max(1, output_height)
            if abs(ratio - 1.0) < 0.05:
                aspect_key = "1:1"
            elif ratio > 1.2:
                aspect_key = "16:9"
            elif abs(ratio - 0.8) < 0.05:
                aspect_key = "4:5"
        hint, _reason = recommend_reframe_mode(
            source_width,
            source_height,
            aspect_key=aspect_key,
        )
        if hint == "blurred_bg":
            return "blurred_bg"
        if hint == "original":
            return "original"
        if enable_face_detection and has_faces:
            return "smart_crop"
        return "center_crop"
    if normalized == "podcast":
        return "smart_crop" if enable_face_detection and has_faces else "center_crop"
    if normalized in {"gaming", "tutorial", "educational"}:
        return "blurred_bg"
    if normalized in {"smart_crop", "center_crop", "blurred_bg", "solid_bg", "original", "manual"}:
        return normalized
    return "center_crop"


def _opencv_ready() -> Any | None:
    """Return a usable OpenCV module, or None when face detection is unavailable."""
    try:
        import cv2  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenCV import failed (%s); smart crop falls back to center", exc)
        return None

    required = ("CascadeClassifier", "VideoCapture", "cvtColor", "data")
    missing = [name for name in required if not hasattr(cv2, name)]
    if missing:
        logger.warning(
            "OpenCV module is incomplete (missing %s). "
            "Reinstall with: pip uninstall -y opencv-python opencv-python-headless cv2 ; "
            "pip install opencv-python-headless==4.10.0.84. Falling back to center crop.",
            ", ".join(missing),
        )
        return None
    return cv2


def detect_subject_x_ratio(
    video_path: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    sample_count: int = 10,
) -> float | None:
    """Estimate horizontal subject position using OpenCV Haar face / upper-body detection."""
    cv2 = _opencv_ready()
    if cv2 is None:
        return None

    try:
        face_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        body_path = cv2.data.haarcascades + "haarcascade_upperbody.xml"
        face_cascade = cv2.CascadeClassifier(face_path)
        body_cascade = cv2.CascadeClassifier(body_path)
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return None
        if face_cascade.empty() and body_cascade.empty():
            capture.release()
            return None

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 1.0

        centers: list[float] = []
        for index in range(sample_count):
            t = start_seconds + (duration_seconds * (index + 0.5) / sample_count)
            frame_idx = max(int(t * fps), 0)
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = (
                face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
                if not face_cascade.empty()
                else []
            )
            dets = list(faces)
            if not dets and not body_cascade.empty():
                bodies = body_cascade.detectMultiScale(
                    gray, scaleFactor=1.05, minNeighbors=3, minSize=(60, 60)
                )
                dets = list(bodies)
            if len(dets) == 0:
                continue
            x, _y, w, _h = max(dets, key=lambda item: item[2] * item[3])
            centers.append((x + w / 2.0) / float(width))

        capture.release()
        if not centers:
            return None
        # Median reduces jumpiness vs mean when a few frames mis-detect.
        centers.sort()
        return centers[len(centers) // 2]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Face detection failed (%s); using center crop", exc)
        return None


def _hex_to_ffmpeg_color(value: str) -> str:
    text = (value or "#000000").lstrip("#")
    if len(text) != 6:
        text = "000000"
    return f"0x{text}"


def _scale(out_w: int, out_h: int, *, mode: str = "force_original_aspect_ratio=decrease") -> str:
    return f"scale={out_w}:{out_h}:{mode}:{_SCALE_FLAGS}"


def _scale_exact(out_w: int, out_h: int) -> str:
    return f"scale={out_w}:{out_h}:{_SCALE_FLAGS}"


def build_reframe_filter(
    *,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
    mode: str,
    face_x_ratio: float | None = None,
    background_color: str = "#000000",
    focal_x: float = 0.5,
    focal_y: float = 0.5,
    manual_crop: dict[str, float] | None = None,
    enable_face_detection: bool = True,
) -> ReframePlan:
    target_mode = _resolve_mode(
        mode,
        has_faces=face_x_ratio is not None,
        enable_face_detection=enable_face_detection,
        source_width=source_width,
        source_height=source_height,
        output_width=output_width,
        output_height=output_height,
    )
    out_w, out_h = output_width, output_height
    src_w = max(source_width, 1)
    src_h = max(source_height, 1)

    if target_mode == "original":
        color = _hex_to_ffmpeg_color(background_color)
        chain = (
            f"{_scale(out_w, out_h)},"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:{color},"
            f"setsar=1"
        )
        return ReframePlan(
            mode=target_mode,
            filter_chain=chain,
            face_x_ratio=face_x_ratio,
            notes="fit original frame padded (no stretch)",
            effective_crop_width=src_w,
            effective_crop_height=src_h,
            linear_upscale=round(min(out_w / src_w, out_h / src_h), 3),
        )

    if target_mode == "blurred_bg":
        # Full frame preserved in foreground; blurred cover fill behind; slight darken.
        chain = (
            f"split[original][bg];"
            f"[bg]{_scale(out_w, out_h, mode='force_original_aspect_ratio=increase')},"
            f"crop={out_w}:{out_h},"
            f"gblur=sigma=18,"
            f"eq=brightness=-0.08:saturation=0.85[blurred];"
            f"[original]{_scale(out_w, out_h)}[fg];"
            f"[blurred][fg]overlay=(W-w)/2:(H-h)/2,"
            f"setsar=1"
        )
        return ReframePlan(
            mode=target_mode,
            filter_chain=chain,
            face_x_ratio=face_x_ratio,
            notes="blurred darkened background; foreground keeps source proportions",
            effective_crop_width=src_w,
            effective_crop_height=src_h,
            linear_upscale=round(min(out_w / src_w, out_h / src_h), 3),
        )

    if target_mode == "solid_bg":
        color = _hex_to_ffmpeg_color(background_color)
        chain = (
            f"{_scale(out_w, out_h)},"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:{color},"
            f"setsar=1"
        )
        return ReframePlan(
            mode=target_mode,
            filter_chain=chain,
            face_x_ratio=face_x_ratio,
            notes="solid background fit",
            effective_crop_width=src_w,
            effective_crop_height=src_h,
            linear_upscale=round(min(out_w / src_w, out_h / src_h), 3),
        )

    if target_mode == "manual" and manual_crop:
        x = max(0.0, min(1.0, float(manual_crop.get("x", 0))))
        y = max(0.0, min(1.0, float(manual_crop.get("y", 0))))
        w = max(0.05, min(1.0 - x, float(manual_crop.get("width", 1))))
        h = max(0.05, min(1.0 - y, float(manual_crop.get("height", 1))))
        crop_w = max(2, int(round(src_w * w)) // 2 * 2)
        crop_h = max(2, int(round(src_h * h)) // 2 * 2)
        crop_x = max(0, min(src_w - crop_w, int(round(src_w * x))))
        crop_y = max(0, min(src_h - crop_h, int(round(src_h * y))))
        if abs(crop_w - out_w) <= 2 and abs(crop_h - out_h) <= 2:
            chain = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},setsar=1"
        else:
            chain = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},{_scale_exact(out_w, out_h)},setsar=1"
        return ReframePlan(
            mode=target_mode,
            filter_chain=chain,
            notes="manual crop",
            effective_crop_width=crop_w,
            effective_crop_height=crop_h,
            linear_upscale=round(max(out_w / max(1, crop_w), out_h / max(1, crop_h)), 3),
        )

    # Crop to target aspect then scale (Lanczos only when size changes).
    target_aspect = out_w / out_h
    crop_h = src_h
    crop_w = int(round(crop_h * target_aspect))
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(round(crop_w / target_aspect))
    crop_w = max(2, crop_w // 2 * 2)
    crop_h = max(2, crop_h // 2 * 2)

    if target_mode == "smart_crop" and face_x_ratio is not None:
        center_x = face_x_ratio * src_w
        x = int(round(center_x - crop_w / 2))
        x = max(0, min(x, src_w - crop_w))
        note = f"smart crop around x_ratio={face_x_ratio:.3f}"
    else:
        center_x = float(focal_x) * src_w
        x = int(round(center_x - crop_w / 2))
        x = max(0, min(x, src_w - crop_w))
        note = "center crop" if abs(focal_x - 0.5) < 0.01 else f"focal crop x={focal_x:.2f}"

    center_y = float(focal_y) * src_h
    y = int(round(center_y - crop_h / 2))
    y = max(0, min(y, src_h - crop_h))

    impact = analyze_crop_impact(
        src_w,
        src_h,
        aspect_key="9:16" if out_h >= out_w else "16:9",
        output_width=out_w,
        output_height=out_h,
    )
    if impact.severe:
        note = f"{note}; WARNING {impact.message}"

    if abs(crop_w - out_w) <= 2 and abs(crop_h - out_h) <= 2:
        chain = f"crop={crop_w}:{crop_h}:{x}:{y},setsar=1"
    else:
        chain = f"crop={crop_w}:{crop_h}:{x}:{y},{_scale_exact(out_w, out_h)},setsar=1"
    return ReframePlan(
        mode=target_mode,
        filter_chain=chain,
        face_x_ratio=face_x_ratio,
        notes=note,
        effective_crop_width=crop_w,
        effective_crop_height=crop_h,
        linear_upscale=round(max(out_w / max(1, crop_w), out_h / max(1, crop_h)), 3),
    )


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
    background_color: str = "#000000",
    focal_x: float = 0.5,
    focal_y: float = 0.5,
    manual_crop: dict[str, float] | None = None,
    enable_face_detection: bool = True,
) -> ReframePlan:
    face_ratio = None
    resolved = (mode or "auto").lower()
    wants_faces = resolved in {"auto", "smart_crop", "podcast", "general"} and enable_face_detection
    if resolved in {"gaming", "tutorial", "educational", "blurred_bg", "original", "fit_original", "solid_bg"}:
        wants_faces = False
    if wants_faces:
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
        background_color=background_color,
        focal_x=focal_x,
        focal_y=focal_y,
        manual_crop=manual_crop,
        enable_face_detection=enable_face_detection,
    )
