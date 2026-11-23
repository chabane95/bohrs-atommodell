"""Application contracts: frame timing, safe failure, options and viewer controls."""

import contextlib
import io
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock, patch

import glfw
from PIL import Image

from bohr_atom import config, export
from bohr_atom.cli import build_parser, main, validate_arguments
from bohr_atom.renderer import RenderSettings
from bohr_atom.viewer import BohrViewer


class InputTests(unittest.TestCase):
    def test_cli_rejects_invalid_values(self) -> None:
        cases = [
            ["render", "--duration", "nan"],
            ["render", "--duration", "inf"],
            ["render", "--fps", "0"],
            ["render", "--fps", "121"],
            ["render", "--n", "0"],
            ["render", "--n", "13"],
            ["render", "--width", "1921"],
            ["render", "--height", "1081"],
            ["render", "--output", "collision.json"],
            ["image", "--output", "wrong.mp4"],
            ["image", "--seconds", "-1"],
            ["image", "--seconds", "nan"],
            ["image", "--seconds", "37"],
            ["view", "--test-frames", "-1"],
            ["render", "--scene", "spectrum", "--n", "2"],
            ["clips", "--n", "1"],
        ]
        parser = build_parser()
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_arguments(parser.parse_args(case))

    def test_scene_defaults_preserve_the_intended_production_states(self) -> None:
        self.assertEqual(export.default_scene_n("quantization"), 3)
        self.assertEqual(export.default_scene_n("spectrum"), 3)
        self.assertEqual(export.default_scene_n("orbit"), config.DEFAULT_N)
        self.assertIsNone(build_parser().parse_args(["clips"]).n)

    def test_invalid_cli_request_never_opens_gpu(self) -> None:
        with (
            patch("sys.argv", ["bohr-atom", "render", "--duration", "nan"]),
            patch("bohr_atom.export.moderngl.create_standalone_context") as factory,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(), 1)
        factory.assert_not_called()

    def test_export_validation_precedes_gpu_work(self) -> None:
        cases = [
            {"scene": "unknown"},
            {"n": 0},
            {"n": 13},
            {"n": True},
            {"scene": "spectrum", "n": 2},
            {"duration": float("nan")},
            {"duration": 0.0},
            {"fps": 0},
            {"fps": 121},
            {"supersample": 0},
            {"output": Path("collision.json")},
        ]
        valid = {
            "scene": "orbit",
            "settings": RenderSettings(width=320, height=180),
            "output": Path("unused.mp4"),
            "n": 1,
            "duration": 1.0,
            "fps": 3,
            "supersample": 1,
        }
        with patch("bohr_atom.export.moderngl.create_standalone_context") as factory:
            for change in cases:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    export.export_video(**(valid | change))
        factory.assert_not_called()


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Mock()
        self.context.info = {"GL_RENDERER": "unit-test renderer"}
        self.renderer = Mock()
        self.renderer.context = self.context
        self.renderer.metadata = {"actual_n": 1, "finite_mass": True}
        self.renderer.render.side_effect = lambda *args, **kwargs: Image.new("RGB", (320, 180))
        self.settings = RenderSettings(width=320, height=180)

    def test_integer_supersampling_averages_all_four_subpixels(self) -> None:
        source = Image.new("RGB", (2, 2))
        source.putdata([(0, 0, 0), (100, 0, 0), (0, 100, 0), (0, 0, 100)])
        renderer = Mock()
        renderer.render.return_value = source
        reduced = export.render_frame(renderer, "orbit", 0.0, 36.0, 1, (1, 1))
        self.assertEqual(reduced.size, (1, 1))
        self.assertEqual(reduced.getpixel((0, 0)), (25, 25, 25))
        reduced.close()

    def test_encoder_failure_preserves_previous_output_and_closes_resources(self) -> None:
        container = Mock()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("bohr_atom.export.moderngl.create_standalone_context", return_value=self.context),
            patch("bohr_atom.export.BohrRenderer", return_value=self.renderer),
            patch("bohr_atom.export.av.open", return_value=container),
            patch("bohr_atom.export.encode_frame", side_effect=RuntimeError("encoder failed")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            output = Path(directory) / "previous.mp4"
            output.write_bytes(b"previous successful export")
            with self.assertRaisesRegex(RuntimeError, "encoder failed"):
                export.export_video(
                    "orbit", self.settings, output, duration=1.0, fps=3, supersample=1
                )
            self.assertEqual(output.read_bytes(), b"previous successful export")
        container.close.assert_called_once()
        self.renderer.close.assert_called_once()
        self.context.release.assert_called_once()

    def test_constructor_failure_releases_context(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("bohr_atom.export.moderngl.create_standalone_context", return_value=self.context),
            patch("bohr_atom.export.BohrRenderer", side_effect=RuntimeError("shader failed")),
            self.assertRaisesRegex(RuntimeError, "shader failed"),
        ):
            export.export_still("orbit", self.settings, Path(directory) / "still.png")
        self.context.release.assert_called_once()

    def test_still_export_does_not_need_optional_encoder(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("bohr_atom.export.av", None),
            patch("bohr_atom.export.moderngl.create_standalone_context", return_value=self.context),
            patch("bohr_atom.export.BohrRenderer", return_value=self.renderer),
        ):
            output = Path(directory) / "still.png"
            export.export_still("orbit", self.settings, output, supersample=1)
            with Image.open(output) as image:
                self.assertEqual(image.size, (320, 180))
                self.assertEqual(image.format, "PNG")
            record = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(record["scene_metadata"]["actual_n"], 1)
            self.assertTrue(record["render_settings"]["finite_mass"])
        self.renderer.close.assert_called_once()
        self.context.release.assert_called_once()

    def test_missing_encoder_is_reported_before_gpu_creation(self) -> None:
        with (
            patch("bohr_atom.export.av", None),
            patch("bohr_atom.export.moderngl.create_standalone_context") as factory,
            self.assertRaisesRegex(RuntimeError, "PyAV"),
        ):
            export.export_video("orbit", self.settings, Path("unused.mp4"), duration=1.0)
        factory.assert_not_called()

    def test_successful_video_has_exact_renderer_times_and_metadata(self) -> None:
        container = Mock()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("bohr_atom.export.moderngl.create_standalone_context", return_value=self.context),
            patch("bohr_atom.export.BohrRenderer", return_value=self.renderer),
            patch("bohr_atom.export.av.open", return_value=container),
            patch("bohr_atom.export.encode_frame") as encode,
            patch("bohr_atom.export.flush_encoder"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            output = Path(directory) / "timed.mp4"
            pending = output.with_name("timed.partial.mp4")
            container.close.side_effect = lambda: pending.write_bytes(b"encoded output")
            export.export_video("orbit", self.settings, output, duration=1.0, fps=3, supersample=1)
            times = [call.args[1] for call in self.renderer.render.call_args_list]
            self.assertEqual(times, [0.0, 1 / 3, 2 / 3])
            indices = [call.args[3] for call in encode.call_args_list]
            self.assertEqual(indices, [0, 1, 2])
            record = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(record["export"]["frames"], 3)
            self.assertEqual(record["export"]["duration_seconds"], 1.0)
            self.assertEqual(output.read_bytes(), b"encoded output")
        self.context.release.assert_called_once()


def write_test_clip(path: Path, color: str) -> None:
    with export.av.open(str(path), "w") as container:
        stream = export.video_stream(container, 320, 180, 2)
        image = Image.new("RGB", (320, 180), color)
        for index in range(2):
            export.encode_frame(container, stream, image, index, 2)
        export.flush_encoder(container, stream)
        image.close()


class CombinationTests(unittest.TestCase):
    def test_fades_reach_background_and_preserve_the_middle_image(self) -> None:
        self.assertEqual(export.fade_opacity(0, 1080, 30), 0.0)
        self.assertEqual(export.fade_opacity(1079, 1080, 30), 0.0)
        self.assertEqual(export.fade_opacity(12, 1080, 30), 1.0)
        self.assertEqual(export.fade_opacity(540, 1080, 30), 1.0)
        self.assertEqual(export.fade_opacity(6, 1080, 30), 0.5)
        with Image.new("RGB", (8, 8), "#aa7711") as original:
            endpoint = export.fade_image(original, 0.0)
            self.assertEqual(endpoint.getpixel((0, 0)), export.FADE_BACKGROUND)
            endpoint.close()
            self.assertIs(export.fade_image(original, 1.0), original)

    def test_short_test_clips_are_not_faded(self) -> None:
        opacities = [export.fade_opacity(index, 4, 30) for index in range(4)]
        self.assertEqual(opacities, [1.0, 1.0, 1.0, 1.0])
        self.assertEqual(export.fade_opacity(0, 1080, 30, fade_seconds=0.0), 1.0)

    def test_combined_clip_has_no_missing_or_duplicate_boundary_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.mp4"
            second = Path(directory) / "second.mp4"
            output = Path(directory) / "combined.mp4"
            write_test_clip(first, "#aa7711")
            write_test_clip(second, "#447799")
            export.combine_clips([first, second], output, 320, 180, 2)
            with export.av.open(str(output)) as container:
                timestamps = [frame.pts * frame.time_base for frame in container.decode(video=0)]
                self.assertFalse(container.streams.audio)
            self.assertEqual(timestamps, [Fraction(0), Fraction(1, 2), Fraction(1), Fraction(3, 2)])
            record = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(record["export"]["frames"], 4)
            self.assertEqual(record["export"]["duration_seconds"], 2.0)
            self.assertEqual([chapter["start_seconds"] for chapter in record["chapters"]], [0, 1])


class ViewerTests(unittest.TestCase):
    def test_scene_selection_wraps_and_spectrum_uses_an_emitting_level(self) -> None:
        viewer = BohrViewer(RenderSettings(width=320, height=180), scene="energy", n=1)
        viewer.on_key(None, glfw.KEY_TAB, 0, glfw.PRESS, 0)
        self.assertEqual(viewer.scene, "spectrum")
        self.assertEqual(viewer.n, 3)
        viewer.on_key(None, glfw.KEY_1, 0, glfw.PRESS, 0)
        self.assertEqual(viewer.n, 3)
        viewer.on_key(None, glfw.KEY_TAB, 0, glfw.PRESS, glfw.MOD_SHIFT)
        self.assertEqual(viewer.scene, "energy")

    def test_pause_and_reset_keep_time_and_manual_camera_consistent(self) -> None:
        viewer = BohrViewer(RenderSettings(width=320, height=180))
        viewer.seconds = 7.0
        viewer.paused = True
        viewer.context = Mock()
        viewer.renderer = Mock()
        viewer.renderer.render.return_value = Image.new("RGB", (320, 180))
        viewer.display_texture = Mock()
        viewer.display_buffer = Mock()
        viewer.render_frame(0.1)
        self.assertEqual(viewer.seconds, 7.0)
        viewer.renderer.render.assert_called_once_with(
            "orbit", 7.0, 36.0, n=1, azimuth=None, elevation=None
        )
        viewer.azimuth = 91.0
        viewer.elevation = 50.0
        viewer.on_key(None, glfw.KEY_R, 0, glfw.PRESS, 0)
        self.assertEqual(viewer.seconds, 0.0)
        self.assertIsNone(viewer.azimuth)
        self.assertIsNone(viewer.elevation)


if __name__ == "__main__":
    unittest.main()
