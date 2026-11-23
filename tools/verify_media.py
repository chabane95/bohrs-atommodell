"""Decode every delivered frame; retain only three stills per individual clip."""

import argparse
import ast
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
from PIL import Image, ImageDraw, ImageFont

SCENES = ("orbit", "vectors", "quantization", "comparison", "energy", "spectrum", "orbital")
COMBINED = "Bohrs_Atommodell_Alle_Szenen.mp4"


class SourceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.depth = 0
        self.nested_lines: list[int] = []
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update(alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self.imports.add(node.module.split(".")[0])

    def visit_loop(self, node: ast.AST) -> None:
        if self.depth:
            self.nested_lines.append(node.lineno)
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    visit_For = visit_loop
    visit_While = visit_loop
    visit_AsyncFor = visit_loop

    def visit_comprehension_expression(self, node: ast.AST) -> None:
        if self.depth or len(node.generators) > 1:
            self.nested_lines.append(node.lineno)
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    visit_ListComp = visit_comprehension_expression
    visit_SetComp = visit_comprehension_expression
    visit_DictComp = visit_comprehension_expression
    visit_GeneratorExp = visit_comprehension_expression


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def inspect_source(project: Path, errors: list[str]) -> dict[str, Any]:
    files = sorted((project / "src").rglob("*.py"))
    for path in files:
        visitor = SourceVisitor()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8-sig")))
        require(
            not visitor.nested_lines, f"{path.name}: nested loops on {visitor.nested_lines}", errors
        )
        require(
            not ({"scipy", "manim"} & visitor.imports),
            f"{path.name}: forbidden production dependency",
            errors,
        )
        if path.name == "physics.py":
            external = visitor.imports - sys.stdlib_module_names - {"bohr_atom", "__future__"}
            require(
                not external, f"Physics core has external dependencies: {sorted(external)}", errors
            )
    return {"python_files": len(files)}


def contact_sheet(images: list[tuple[Image.Image, str]], output: Path) -> None:
    if not images:
        return
    tile_width, tile_height, caption = 480, 270, 28
    rows = (len(images) + 2) // 3
    sheet = Image.new("RGB", (tile_width * 3, rows * (tile_height + caption)), "#15191b")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=17)
    for index, (image, label) in enumerate(images):
        x = index % 3 * tile_width
        y = index // 3 * (tile_height + caption)
        sheet.paste(image, (x, y + caption))
        draw.text((x + 8, y + 5), label, fill="#e2d7c4", font=font)
    sheet.save(output, quality=92)


def inspect_mp4(
    path: Path, args: argparse.Namespace, errors: list[str], captures: list[tuple[Image.Image, str]]
) -> dict[str, Any]:
    combined = path.name == COMBINED
    expected_duration = args.duration * len(SCENES) if combined else args.duration
    expected_count = round(expected_duration * args.fps)
    targets = (
        set()
        if combined
        else {round((expected_count - 1) * fraction) for fraction in (0.12, 0.5, 0.88)}
    )
    frames = 0
    wrong_dimensions = 0
    missing_pts = 0
    nonmonotonic_pts = 0
    maximum_time_error = 0.0
    previous_time: Fraction | None = None
    with av.open(str(path)) as container:
        require(
            len(container.streams.video) == 1 and not container.streams.audio,
            f"{path.name}: expected one silent video stream",
            errors,
        )
        stream = container.streams.video[0]
        require(stream.codec_context.name == "h264", f"{path.name}: codec is not H.264", errors)
        require(
            stream.codec_context.pix_fmt == "yuv420p", f"{path.name}: pixel format differs", errors
        )
        require(stream.average_rate == Fraction(args.fps), f"{path.name}: FPS differs", errors)
        for frame in container.decode(stream):
            wrong_dimensions += (frame.width, frame.height) != (args.width, args.height)
            if frame.pts is None or frame.time_base is None:
                missing_pts += 1
            else:
                timestamp = frame.pts * frame.time_base
                maximum_time_error = max(
                    maximum_time_error, float(abs(timestamp - Fraction(frames, args.fps)))
                )
                if previous_time is not None and timestamp <= previous_time:
                    nonmonotonic_pts += 1
                previous_time = timestamp
            if frames in targets:
                image = frame.to_image()
                image.save(args.report / f"{path.stem}_{frames:04d}.png")
                image = image.resize((480, 270), Image.Resampling.LANCZOS)
                captures.append((image, f"{path.stem} | {frames / args.fps:.2f} s"))
            frames += 1
        duration = None if stream.duration is None else float(stream.duration * stream.time_base)
    require(
        frames == expected_count, f"{path.name}: {frames} frames, expected {expected_count}", errors
    )
    require(wrong_dimensions == 0, f"{path.name}: frames with wrong dimensions", errors)
    require(missing_pts == 0 and nonmonotonic_pts == 0, f"{path.name}: invalid PTS", errors)
    require(maximum_time_error <= 1e-6, f"{path.name}: irregular frame timing", errors)
    require(
        duration is not None and abs(duration - expected_duration) <= 1e-5,
        f"{path.name}: duration {duration}, expected {expected_duration}",
        errors,
    )
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8-sig"))
    exported = metadata["export"]
    require(
        exported.get("frames") == frames and exported.get("fps") == args.fps,
        f"{path.name}: metadata timing mismatch",
        errors,
    )
    require(
        exported.get("width") == args.width and exported.get("height") == args.height,
        f"{path.name}: metadata resolution mismatch",
        errors,
    )
    require(
        abs(exported.get("duration_seconds", -1) - expected_duration) <= 1e-6,
        f"{path.name}: metadata duration mismatch",
        errors,
    )
    if combined:
        chapters = metadata.get("chapters", [])
        require(len(chapters) == len(SCENES), f"{path.name}: incomplete chapters", errors)
        starts = [chapter.get("start_seconds") for chapter in chapters]
        require(
            starts == [index * args.duration for index in range(len(SCENES))],
            f"{path.name}: chapter boundaries differ",
            errors,
        )
    else:
        scene = path.stem.split("_", 1)[1]
        require(exported.get("scene") == scene, f"{path.name}: scene metadata differs", errors)
    return {
        "file": path.name,
        "frames": frames,
        "duration_seconds": duration,
        "maximum_timestamp_error_seconds": maximum_time_error,
        "scene": exported.get("scene"),
        "n": exported.get("n"),
        "finite_mass": metadata.get("render_settings", {}).get("finite_mass"),
    }


def inspect_plots(directory: Path, errors: list[str]) -> dict[str, Any]:
    paths = sorted(directory.glob("*.png"))
    require(bool(paths), "No plot PNGs found", errors)
    for path in paths:
        try:
            with Image.open(path) as image:
                image.load()
                require(image.size == (3840, 2160), f"{path.name}: plot is not 4K 16:9", errors)
        except OSError as error:
            errors.append(f"{path.name}: {error}")
    return {"decoded_pngs": len(paths)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", type=Path, default=Path("outputs/clips"))
    parser.add_argument("--report", type=Path, default=Path("outputs/qa_media"))
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--files", nargs="+", default=None)
    parser.add_argument("--skip-combined", action="store_true")
    parser.add_argument("--skip-source", action="store_true")
    parser.add_argument("--plots", type=Path, default=None)
    parser.add_argument("--duration", type=float, default=36.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=True)
    filenames = args.files or [f"{index:02d}_{scene}.mp4" for index, scene in enumerate(SCENES, 1)]
    if not args.skip_combined and COMBINED not in filenames:
        filenames.append(COMBINED)
    errors: list[str] = []
    report: dict[str, Any] = {}
    if not args.skip_source:
        report["source"] = inspect_source(args.project, errors)
    captures: list[tuple[Image.Image, str]] = []
    records: list[dict[str, Any]] = []
    for filename in filenames:
        print(f"Decoding {filename}", flush=True)
        try:
            records.append(inspect_mp4(args.clips / filename, args, errors, captures))
        except Exception as error:
            errors.append(f"{filename}: {type(error).__name__}: {error}")
    contact_sheet(captures, args.report / "contact.jpg")
    report["videos"] = records
    if args.plots is not None:
        report["plots"] = inspect_plots(args.plots, errors)
    report["passed"] = not errors
    report["errors"] = errors
    path = args.report / "verification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"passed": not errors, "errors": len(errors), "report": str(path.resolve())}),
        flush=True,
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
