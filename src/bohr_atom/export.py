"""PNG and constant-frame-rate H.264 exports through the shared renderer.

Individual clips retain their original frames. The combined film gently fades
long clips to the light background without inserting or removing frames.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import moderngl
from PIL import Image

from bohr_atom import config
from bohr_atom.renderer import BohrRenderer, RenderSettings

try:
    import av
except ImportError:
    av = None


def default_scene_n(scene: str) -> int:
    return 3 if scene in ("quantization", "spectrum") else config.DEFAULT_N


def validate_scene(scene: str, n: int, duration: float) -> None:
    if scene not in config.SCENES:
        raise ValueError(f"Unknown scene: {scene}")
    if type(n) is not int or not 1 <= n <= 12:
        raise ValueError("n must be an integer between 1 and 12.")
    if scene == "spectrum" and n < 3:
        raise ValueError("The spectrum scene requires n >= 3 for the transition to n = 2.")
    if not math.isfinite(duration) or not 1.0 <= duration <= 600.0:
        raise ValueError("Duration must be finite and between 1 and 600 seconds.")


def validate_render(settings: RenderSettings, supersample: int) -> None:
    if type(settings.width) is not int or type(settings.height) is not int:
        raise ValueError("Image dimensions must be integers.")
    if settings.width < 320 or settings.height < 180:
        raise ValueError("Resolution must be at least 320 x 180.")
    if type(supersample) is not int or supersample not in (1, 2, 3):
        raise ValueError("Supersampling must be 1, 2 or 3.")


def validate_video(settings: RenderSettings, fps: int, output: Path) -> None:
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("Frame rate must be an integer between 1 and 120.")
    if settings.width % 2 or settings.height % 2:
        raise ValueError("H.264 export requires even width and height.")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Video output must use the .mp4 extension.")


def require_encoder() -> None:
    if av is None:
        raise RuntimeError('Video export needs PyAV: pip install -e ".[video]"')


def json_default(value: Any) -> Any:
    """Accept renderer diagnostics containing NumPy values, without importing NumPy here."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Metadata value cannot be serialized: {type(value).__name__}")


def write_pending_metadata(output: Path, record: dict[str, Any]) -> Path:
    pending = output.with_name(output.stem + ".json.pending")
    pending.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    return pending


def metadata_record(
    renderer: BohrRenderer, settings: RenderSettings, details: dict[str, Any]
) -> dict[str, Any]:
    scene_metadata = getattr(renderer, "metadata", {})
    if "n" in details and "actual_n" in scene_metadata:
        details = details | {"requested_n": details["n"], "n": scene_metadata["actual_n"]}
    return {
        "render_settings": asdict(settings),
        "renderer": renderer.context.info.get("GL_RENDERER", "unknown"),
        "scene_metadata": scene_metadata,
        "export": details,
    }


def close_renderer(renderer: BohrRenderer | None, context: moderngl.Context) -> None:
    try:
        if renderer is not None:
            renderer.close()
    finally:
        context.release()


def render_frame(
    renderer: BohrRenderer,
    scene: str,
    seconds: float,
    duration: float,
    n: int,
    size: tuple[int, int],
) -> Image.Image:
    source = renderer.render(scene, seconds, duration, n=n)
    if source.size == size:
        return source
    try:
        factor = source.width // size[0]
        if factor in (2, 3) and source.size == (size[0] * factor, size[1] * factor):
            return source.reduce(factor)
        return source.resize(size, Image.Resampling.LANCZOS)
    finally:
        source.close()


def export_still(
    scene: str,
    settings: RenderSettings,
    output: Path,
    n: int | None = None,
    seconds: float = 18.0,
    duration: float = 36.0,
    supersample: int = 2,
) -> None:
    n = default_scene_n(scene) if n is None else n
    validate_scene(scene, n, duration)
    validate_render(settings, supersample)
    if output.suffix.lower() != ".png":
        raise ValueError("Image output must use the .png extension.")
    if not math.isfinite(seconds) or not 0.0 <= seconds <= duration:
        raise ValueError("Image time must lie between zero and the scene duration.")
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(output.name + ".pending")
    context = moderngl.create_standalone_context(require=330)
    renderer: BohrRenderer | None = None
    try:
        internal = replace(
            settings, width=settings.width * supersample, height=settings.height * supersample
        )
        renderer = BohrRenderer(context, internal)
        image = render_frame(
            renderer, scene, seconds, duration, n, (settings.width, settings.height)
        )
        try:
            image.save(pending, format="PNG")
        finally:
            image.close()
        record = metadata_record(
            renderer,
            settings,
            {
                "kind": "still",
                "scene": scene,
                "n": n,
                "seconds": seconds,
                "duration_seconds": duration,
                "width": settings.width,
                "height": settings.height,
                "supersample": supersample,
            },
        )
        pending_metadata = write_pending_metadata(output, record)
        pending.replace(output)
        pending_metadata.replace(output.with_suffix(".json"))
    finally:
        close_renderer(renderer, context)


def encode_frame(container: Any, stream: Any, image: Image.Image, index: int, fps: int) -> None:
    frame = av.VideoFrame.from_image(image)
    frame.pts = index
    frame.time_base = Fraction(1, fps)
    for packet in stream.encode(frame):
        container.mux(packet)


def flush_encoder(container: Any, stream: Any) -> None:
    for packet in stream.encode():
        container.mux(packet)


def video_stream(container: Any, width: int, height: int, fps: int) -> Any:
    stream = container.add_stream("libx264", rate=fps)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "18", "preset": "medium"}
    return stream


def export_video(
    scene: str,
    settings: RenderSettings,
    output: Path,
    n: int | None = None,
    duration: float = 36.0,
    fps: int = 30,
    supersample: int = 2,
) -> None:
    n = default_scene_n(scene) if n is None else n
    validate_scene(scene, n, duration)
    validate_render(settings, supersample)
    validate_video(settings, fps, output)
    require_encoder()
    total_frames = round(duration * fps)
    actual_duration = total_frames / fps
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(output.stem + ".partial.mp4")
    context = moderngl.create_standalone_context(require=330)
    renderer: BohrRenderer | None = None
    container: Any = None
    try:
        internal = replace(
            settings, width=settings.width * supersample, height=settings.height * supersample
        )
        renderer = BohrRenderer(context, internal)
        container = av.open(str(pending), "w", options={"movflags": "+faststart"})
        stream = video_stream(container, settings.width, settings.height, fps)
        print(f"{scene}: {context.info.get('GL_RENDERER', 'OpenGL')}", flush=True)
        for index in range(total_frames):
            seconds = index / fps
            image = render_frame(
                renderer, scene, seconds, actual_duration, n, (settings.width, settings.height)
            )
            try:
                encode_frame(container, stream, image, index, fps)
            finally:
                image.close()
            if index % (fps * 6) == 0:
                print(f"{scene}: {seconds:.0f}/{actual_duration:g} s", flush=True)
        flush_encoder(container, stream)
        container.close()
        container = None
        record = metadata_record(
            renderer,
            settings,
            {
                "kind": "video",
                "scene": scene,
                "n": n,
                "frames": total_frames,
                "fps": fps,
                "duration_seconds": actual_duration,
                "requested_duration_seconds": duration,
                "width": settings.width,
                "height": settings.height,
                "supersample": supersample,
            },
        )
        pending_metadata = write_pending_metadata(output, record)
        pending.replace(output)
        pending_metadata.replace(output.with_suffix(".json"))
    finally:
        try:
            if container is not None:
                container.close()
        finally:
            close_renderer(renderer, context)


FADE_BACKGROUND: tuple[int, int, int] = (247, 246, 240)


def fade_opacity(frame_index: int, frame_count: int, fps: int, fade_seconds: float = 0.4) -> float:
    """Image opacity with exact background endpoints and cubic easing."""
    if fade_seconds == 0.0 or frame_count < 2 * fps:
        return 1.0
    fade_frames = min(fade_seconds * fps, (frame_count - 1) / 2.0)
    distance_from_edge = min(frame_index, frame_count - 1 - frame_index)
    progress = max(0.0, min(1.0, distance_from_edge / fade_frames))
    return progress * progress * (3.0 - 2.0 * progress)


def fade_image(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1.0:
        return image
    background = Image.new("RGB", image.size, FADE_BACKGROUND)
    try:
        return Image.blend(background, image, opacity)
    finally:
        background.close()


def append_clip(
    container: Any,
    stream: Any,
    path: Path,
    first_frame: int,
    width: int,
    height: int,
    fps: int,
    fade_seconds: float = 0.4,
) -> int:
    next_frame = first_frame
    with av.open(str(path)) as source:
        if len(source.streams.video) != 1 or source.streams.audio:
            raise ValueError(f"Expected one silent video stream: {path}")
        video = source.streams.video[0]
        if video.average_rate != Fraction(fps):
            raise ValueError(f"Clip frame rate differs from the combined film: {path}")
        declared_frames = video.frames
        if declared_frames <= 0 and video.duration is not None:
            declared_frames = round(float(video.duration * video.time_base) * fps)
        for frame in source.decode(video=0):
            if (frame.width, frame.height) != (width, height):
                raise ValueError(f"Clip dimensions differ from the combined film: {path}")
            image = frame.to_image()
            opacity = fade_opacity(next_frame - first_frame, declared_frames, fps, fade_seconds)
            blended = fade_image(image, opacity)
            try:
                encode_frame(container, stream, blended, next_frame, fps)
            finally:
                if blended is not image:
                    blended.close()
                image.close()
            next_frame += 1
        if declared_frames > 0 and next_frame - first_frame != declared_frames:
            raise ValueError(f"Clip frame count differs from its header: {path}")
    return next_frame


def combine_clips(
    paths: list[Path], output: Path, width: int, height: int, fps: int, fade_seconds: float = 0.4
) -> None:
    settings = RenderSettings(width=width, height=height)
    validate_render(settings, 1)
    validate_video(settings, fps, output)
    if not math.isfinite(fade_seconds) or fade_seconds < 0.0:
        raise ValueError("Fade duration must be finite and nonnegative.")
    if not paths:
        raise ValueError("At least one clip is required.")
    if output.resolve() in {path.resolve() for path in paths}:
        raise ValueError("The combined output must differ from its source clips.")
    require_encoder()
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(output.stem + ".partial.mp4")
    with av.open(str(pending), "w", options={"movflags": "+faststart"}) as container:
        stream = video_stream(container, width, height, fps)
        count = 0
        chapters: list[dict[str, Any]] = []
        for path in paths:
            start = count
            count = append_clip(container, stream, path, count, width, height, fps, fade_seconds)
            chapters.append(
                {
                    "file": path.name,
                    "start_seconds": start / fps,
                    "end_seconds": count / fps,
                    "frames": count - start,
                }
            )
        flush_encoder(container, stream)
    record = {
        "export": {
            "kind": "combined",
            "frames": count,
            "fps": fps,
            "duration_seconds": count / fps,
            "width": width,
            "height": height,
            "fade_seconds": fade_seconds,
            "fade_background_rgb": list(FADE_BACKGROUND),
            "fade_minimum_clip_seconds": 2.0,
        },
        "chapters": chapters,
    }
    pending_metadata = write_pending_metadata(output, record)
    pending.replace(output)
    pending_metadata.replace(output.with_suffix(".json"))


def export_all_clips(
    output: Path,
    settings: RenderSettings | None = None,
    n: int | None = None,
    duration: float = config.CLIP_SECONDS,
    fps: int = config.FPS,
    supersample: int = config.SUPERSAMPLE,
) -> None:
    if n is not None and "spectrum" in config.SCENES:
        validate_scene("spectrum", n, duration)
    if settings is None:
        settings = RenderSettings(
            width=config.WIDTH, height=config.HEIGHT, finite_mass=config.FINITE_MASS
        )
    paths: list[Path] = []
    for index, scene in enumerate(config.SCENES, start=1):
        path = output / f"{index:02d}_{scene}.mp4"
        export_video(
            scene, settings, path, n=n, duration=duration, fps=fps, supersample=supersample
        )
        paths.append(path)
    combine_clips(
        paths, output / "Bohrs_Atommodell_Alle_Szenen.mp4", settings.width, settings.height, fps
    )
