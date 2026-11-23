"""Output-contract checks for independently usable frames and scientific figures."""

import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from bohr_atom.presentation import (
    Axes,
    Canvas,
    _energy_panel,
    _font,
    _number,
    _spectrum_panel,
    draw_overlay,
    export_plots,
)


class FigureTests(unittest.TestCase):
    def test_six_complete_raster_and_standalone_vector_figures(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = export_plots(Path(temporary), width=960, height=540)
            self.assertEqual(len(paths), 12)
            self.assertEqual(len(set(paths)), 12)
            for path in paths:
                self.assertGreater(path.stat().st_size, 1000)
                if path.suffix == ".png":
                    with Image.open(path) as picture:
                        picture.load()
                        self.assertEqual(picture.size, (960, 540))
                        self.assertEqual(picture.mode, "RGB")
                else:
                    root = ET.parse(path).getroot()
                    self.assertEqual(root.attrib["viewBox"], "0 0 960 540")
                    self.assertTrue(root.tag.endswith("svg"))
                    self.assertNotIn("<image", path.read_text(encoding="utf-8"))
                    self.assertIn("Wasserstoff", "".join(root.itertext()))

    def test_linear_axes_preserve_data_endpoints_and_midpoints(self):
        axes = Axes(Canvas(1920, 1080), (1, 7), (-14, 0))
        self.assertEqual(axes.point(1, -14), (axes.left, axes.bottom))
        right, top = axes.point(7, 0)
        self.assertAlmostEqual(right, axes.right)
        self.assertAlmostEqual(top, axes.top)
        x, y = axes.point(4, -7)
        self.assertAlmostEqual(x, (axes.left + axes.right) / 2)
        self.assertAlmostEqual(y, (axes.top + axes.bottom) / 2)

    def test_curve_clipping_never_connects_across_an_invalid_interval(self):
        canvas = Canvas(960, 540)
        axes = Axes(canvas, (0, 4), (0, 2))
        axes.curve(lambda x: math.nan if 1 < x < 3 else 1)
        polylines = [element for element in canvas.svg if element.startswith("<polyline")]
        self.assertEqual(len(polylines), 2)

    def test_small_export_is_rejected_before_files_are_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "not-created"
            with self.assertRaises(ValueError):
                export_plots(output, width=300, height=200)
            self.assertFalse(output.exists())

    def test_decimal_formatting_preserves_integer_trailing_zeros(self):
        self.assertEqual(_number(100, 0), "100")
        self.assertEqual(_number(-13.5984, 2), "−13,6")


class OverlayTests(unittest.TestCase):
    def test_highest_state_energy_panel_contains_selected_level(self):
        canvas = Canvas(1920, 1080)
        _energy_panel(canvas, 12, True, (1133, 238, 1805, 842))
        root = ET.fromstring("<svg>" + "".join(canvas.svg) + "</svg>")
        selected = [element for element in root.iter("text") if element.text == "n=12"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].attrib["fill"], "#C58B1D")

    def test_highest_state_spectrum_labels_stay_inside_panel(self):
        canvas = Canvas(1920, 1080)
        metadata = {"transition_initial": 12, "transition_final": 2, "transition_progress": 0.5}
        _spectrum_panel(canvas, True, metadata, (1133, 238, 1805, 842))
        root = ET.fromstring("<svg>" + "".join(canvas.svg) + "</svg>")
        texts = list(root.iter("text"))
        self.assertIn("n=12", [element.text for element in texts])
        self.assertTrue(any("Vakuum" in (element.text or "") for element in texts))
        self.assertIn("360", [element.text for element in texts])
        labels = [element for element in texts if (element.text or "").startswith("n=")]
        positions = sorted(float(element.attrib["y"]) for element in labels)
        self.assertGreaterEqual(min(positions), 238)
        self.assertLessEqual(max(positions), 842)
        spacings = [second - first for first, second in zip(positions, positions[1:], strict=False)]
        self.assertGreaterEqual(min(spacings), 24)

    def test_overlay_keeps_source_frame_and_produces_rgb(self):
        source = Image.new("RGBA", (960, 540), (211, 220, 213, 255))
        original = source.tobytes()
        frame = draw_overlay(source, "orbit", 1, True, 0, 22, {})
        self.assertEqual(source.tobytes(), original)
        self.assertEqual(frame.mode, "RGB")
        self.assertEqual(frame.size, source.size)
        self.assertNotEqual(frame.tobytes(), source.convert("RGB").tobytes())

    def test_all_production_scenes_accept_renderer_metadata(self):
        source = Image.new("RGB", (960, 540), "#EFF2F1")
        metadata = {
            "screen_points": {"p": (200, 220), "e": (420, 300), "r_mid": (310, 260)},
            "panel_labels": [
                {"n": 1, "x": 240, "y": 420},
                {"text": "1s · |ψ|²", "x": 720, "y": 420},
            ],
            "time_scale_s_per_video_s": 3.0e-17,
            "transition_initial": 4,
            "transition_final": 2,
            "transition_progress": 0.5,
        }
        scenes = ("orbit", "vectors", "quantization", "comparison", "energy", "spectrum", "orbital")
        for scene in scenes:
            with self.subTest(scene=scene):
                frame = draw_overlay(source, scene, 4, True, 5, 22, metadata)
                self.assertEqual(frame.size, source.size)

    @unittest.skipUnless(Path("C:/Windows/Fonts/cambria.ttc").exists(), "Windows font regression")
    def test_mathematical_glyphs_do_not_use_the_missing_character_box(self):
        font = _font(40, mathematical=True)
        missing = bytes(font.getmask("\uffff"))
        for character in "ℏₙₑₚ⁺⁻⟨⟩→∝":
            self.assertNotEqual(bytes(font.getmask(character)), missing, character)


if __name__ == "__main__":
    unittest.main()
