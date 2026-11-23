"""Explicit scene selection and input validation before opening GPU resources."""

import argparse
import math
import sys
from pathlib import Path

import moderngl

from bohr_atom import config
from bohr_atom.renderer import RenderSettings


def display_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--n", type=int, default=None, help="Principal quantum number; scene defaults are 1 or 3."
    )
    parser.add_argument("--width", type=int, default=config.WIDTH)
    parser.add_argument("--height", type=int, default=config.HEIGHT)
    parser.add_argument("--fixed-nucleus", action="store_true")
    parser.add_argument("--no-labels", action="store_true")


def video_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--duration", type=float, default=config.CLIP_SECONDS)
    parser.add_argument("--fps", type=int, default=config.FPS)
    parser.add_argument("--supersample", type=int, choices=(1, 2, 3), default=config.SUPERSAMPLE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Das Bohrsche Atommodell in ruhigen 3D-Szenen.")
    commands = parser.add_subparsers(dest="command", required=True)
    viewer = commands.add_parser("view", help="Interaktive Vorschau öffnen.")
    display_arguments(viewer)
    viewer.set_defaults(width=1280, height=720)
    viewer.add_argument("--scene", choices=config.SCENES, default="orbit")
    viewer.add_argument("--duration", type=float, default=config.CLIP_SECONDS)
    viewer.add_argument("--test-frames", type=int, default=0, help=argparse.SUPPRESS)
    image = commands.add_parser("image", help="Ein PNG exportieren.")
    display_arguments(image)
    image.add_argument("--scene", choices=config.SCENES, default="orbit")
    image.add_argument("--output", type=Path, default=Path("outputs/bohr.png"))
    image.add_argument("--seconds", type=float, default=None)
    image.add_argument("--duration", type=float, default=config.CLIP_SECONDS)
    image.add_argument("--supersample", type=int, choices=(1, 2, 3), default=config.SUPERSAMPLE)
    render = commands.add_parser("render", help="Eine Szene als H.264-MP4 exportieren.")
    display_arguments(render)
    video_arguments(render)
    render.add_argument("--scene", choices=config.SCENES, default="orbit")
    render.add_argument("--output", type=Path, default=Path("outputs/bohr-preview.mp4"))
    clips = commands.add_parser("clips", help="Sieben Szenen und einen Gesamtfilm exportieren.")
    display_arguments(clips)
    video_arguments(clips)
    clips.add_argument("--output", type=Path, default=Path("outputs/clips"))
    plots = commands.add_parser(
        "plots", help="Eigenständige wissenschaftliche Diagramme exportieren."
    )
    plots.add_argument("--output", type=Path, default=Path("outputs/plots"))
    plots.add_argument("--fixed-nucleus", action="store_true")
    plots.add_argument("--width", type=int, default=3840)
    plots.add_argument("--height", type=int, default=2160)
    return parser


def validate_arguments(args: argparse.Namespace) -> None:
    if args.width < 320 or args.height < 180:
        raise ValueError("Resolution must be at least 320 x 180.")
    if args.command == "plots":
        return
    if args.n is not None and not 1 <= args.n <= 12:
        raise ValueError("n must lie between 1 and 12.")
    if (
        args.n is not None
        and args.n < 3
        and (args.command == "clips" or getattr(args, "scene", None) == "spectrum")
    ):
        raise ValueError("The spectrum scene requires n >= 3; omit --n for scene defaults.")
    if not math.isfinite(args.duration) or not 1.0 <= args.duration <= 600.0:
        raise ValueError("Duration must be finite and between 1 and 600 seconds.")
    if args.command == "view":
        if args.test_frames < 0:
            raise ValueError("Test frame count must be nonnegative.")
        return
    if args.command == "image":
        if args.output.suffix.lower() != ".png":
            raise ValueError("Image output must use the .png extension.")
        if args.seconds is not None and (
            not math.isfinite(args.seconds) or not 0.0 <= args.seconds <= args.duration
        ):
            raise ValueError("Image time must lie within the scene duration.")
        return
    if not 1 <= args.fps <= 120:
        raise ValueError("Frame rate must be between 1 and 120.")
    if args.width % 2 or args.height % 2:
        raise ValueError("H.264 export requires even width and height.")
    if args.command == "render" and args.output.suffix.lower() != ".mp4":
        raise ValueError("Video output must use the .mp4 extension.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] or ["view"])
    try:
        validate_arguments(args)
        finite_mass = config.FINITE_MASS and not args.fixed_nucleus
        if args.command == "plots":
            from bohr_atom.presentation import export_plots

            export_plots(args.output, finite_mass=finite_mass, width=args.width, height=args.height)
            print(f"Saved plots: {args.output.resolve()}")
            return 0
        settings = RenderSettings(
            width=args.width, height=args.height, labels=not args.no_labels, finite_mass=finite_mass
        )
        if args.command == "view":
            from bohr_atom.export import default_scene_n
            from bohr_atom.viewer import BohrViewer

            n = default_scene_n(args.scene) if args.n is None else args.n
            BohrViewer(
                settings,
                scene=args.scene,
                n=n,
                duration=args.duration,
                test_frames=args.test_frames,
            ).run()
        elif args.command == "image":
            from bohr_atom.export import export_still

            seconds = args.duration / 2.0 if args.seconds is None else args.seconds
            export_still(
                args.scene,
                settings,
                args.output,
                n=args.n,
                seconds=seconds,
                duration=args.duration,
                supersample=args.supersample,
            )
            print(f"Saved: {args.output.resolve()}")
        elif args.command == "render":
            from bohr_atom.export import export_video

            export_video(
                args.scene,
                settings,
                args.output,
                n=args.n,
                duration=args.duration,
                fps=args.fps,
                supersample=args.supersample,
            )
            print(f"Saved: {args.output.resolve()}")
        elif args.command == "clips":
            from bohr_atom.export import export_all_clips

            export_all_clips(
                args.output,
                settings,
                n=args.n,
                duration=args.duration,
                fps=args.fps,
                supersample=args.supersample,
            )
            print(f"Saved clips: {args.output.resolve()}")
    except (ValueError, RuntimeError, OSError, ArithmeticError, moderngl.Error) as error:
        print(f"bohr-atom: {error}", file=sys.stderr)
        return 1
    except ImportError as error:
        print(
            f'Missing optional component: {error}. Install: pip install -e ".[all]"',
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    return 0
