"""Quiet scientific labels and reproducible Pillow/SVG figures for the Bohr model.

All physical values come from physics.py.  Plotting and screen geometry live here.
The only external dependency of this module is Pillow.
"""

from __future__ import annotations

import html
import math
from functools import lru_cache
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from bohr_atom.physics import BohrState, transition

BACKGROUND = "#EFF2F1"
GOLD = "#C58B1D"
INK = "#393D3E"
MUTED = "#747D7C"
GRID = "#D7DEDA"
TEAL = "#397B80"
RUST = "#AD6A4C"


@lru_cache(maxsize=128)
def _font(
    size: int, bold: bool = False, mathematical: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    filename = "georgiab.ttf" if bold else "georgia.ttf"
    if mathematical:
        filename = "cambriab.ttf" if bold else "cambria.ttc"
    candidates = (
        Path("C:/Windows/Fonts") / filename,
        Path("/usr/share/fonts/truetype/dejavu")
        / ("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/liberation2")
        / ("LiberationSerif-Bold.ttf" if bold else "LiberationSerif-Regular.ttf"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), max(8, int(size)))
    return ImageFont.load_default(size=max(8, int(size)))


def _number(value: float, decimals: int = 2) -> str:
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace("-", "−").replace(".", ",")


class Canvas:
    """One drawing description produces matching raster and editable vector files."""

    def __init__(self, width: int, height: int, image: Image.Image | None = None) -> None:
        self.width = width
        self.height = height
        self.image = image if image is not None else Image.new("RGB", (width, height), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)
        self.scale = min(width / 1920.0, height / 1080.0)
        self.svg: list[str] = []
        self.rectangle((0, 0, width, height), BACKGROUND, raster=image is None)

    def text(
        self,
        position: tuple[float, float],
        text: str,
        size: float = 30,
        color: str = INK,
        anchor: str = "start",
        bold: bool = False,
    ) -> None:
        font_size = max(8, round(size * self.scale))
        mathematical = any(character in "ℏ₀₁₂₃₄₅₆₇₈₉ₙₑₚₛ⁺⁻⟨⟩→∝" for character in text)
        font = _font(font_size, bold, mathematical)
        family = (
            "Cambria, DejaVu Serif, serif" if mathematical else "Georgia, Liberation Serif, serif"
        )
        x, y = position
        left = x
        text_width = self.draw.textlength(text, font=font)
        if anchor == "middle":
            left -= text_width / 2
        elif anchor == "end":
            left -= text_width
        self.draw.text((left, y), text, font=font, fill=color, anchor="lt")
        weight = "bold" if bold else "normal"
        self.svg.append(
            f'<text x="{x:.3f}" y="{y:.3f}" fill="{color}" font-size="{font_size}" '
            f'font-family="{family}" font-weight="{weight}" '
            f'text-anchor="{anchor}" dominant-baseline="hanging">{html.escape(text)}</text>'
        )

    def line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        color: str = INK,
        width: float = 1.5,
        dashed: bool = False,
    ) -> None:
        stroke = max(1, round(width * self.scale))
        if dashed:
            self._dashed_raster(start, end, color, stroke)
        else:
            self.draw.line((start, end), fill=color, width=stroke)
        dash = f' stroke-dasharray="{8 * self.scale:.2f} {7 * self.scale:.2f}"' if dashed else ""
        self.svg.append(
            f'<line x1="{start[0]:.3f}" y1="{start[1]:.3f}" '
            f'x2="{end[0]:.3f}" y2="{end[1]:.3f}" stroke="{color}" '
            f'stroke-width="{stroke}"{dash}/>'
        )

    def _dashed_raster(self, start: tuple, end: tuple, color: str, width: int) -> None:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.hypot(dx, dy)
        if distance == 0:
            return
        step = max(3.0, 15 * self.scale)
        position = 0.0
        while position < distance:
            stop = min(distance, position + step * 8 / 15)
            first = (start[0] + dx * position / distance, start[1] + dy * position / distance)
            last = (start[0] + dx * stop / distance, start[1] + dy * stop / distance)
            self.draw.line((first, last), fill=color, width=width)
            position += step

    def polyline(self, points: list[tuple[float, float]], color: str, width: float = 3) -> None:
        if len(points) < 2:
            return
        stroke = max(1, round(width * self.scale))
        self.draw.line(points, fill=color, width=stroke, joint="curve")
        encoded = " ".join(map(lambda point: f"{point[0]:.3f},{point[1]:.3f}", points))
        self.svg.append(
            f'<polyline points="{encoded}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    def rectangle(self, box: tuple, color: str, raster: bool = True) -> None:
        if raster:
            self.draw.rectangle(box, fill=color)
        x0, y0, x1, y1 = box
        self.svg.append(
            f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{x1 - x0:.3f}" '
            f'height="{y1 - y0:.3f}" fill="{color}"/>'
        )

    def dot(self, center: tuple, radius: float = 5, color: str = GOLD) -> None:
        x, y = center
        r = radius * self.scale
        self.draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        self.svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" fill="{color}"/>')

    def arrow(self, start: tuple, end: tuple, color: str = GOLD, width: float = 2.5) -> None:
        if math.hypot(end[0] - start[0], end[1] - start[1]) < 1.5 * self.scale:
            return
        self.line(start, end, color, width)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        length = 11 * self.scale
        first = (end[0] - length * math.cos(angle - 0.45), end[1] - length * math.sin(angle - 0.45))
        second = (
            end[0] - length * math.cos(angle + 0.45),
            end[1] - length * math.sin(angle + 0.45),
        )
        self.line(end, first, color, width)
        self.line(end, second, color, width)

    def save(self, base: Path) -> list[Path]:
        base.parent.mkdir(parents=True, exist_ok=True)
        png = base.with_suffix(".png")
        svg = base.with_suffix(".svg")
        self.image.save(png)
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}">\n'
            + "\n".join(self.svg)
            + "\n</svg>\n"
        )
        svg.write_text(content, encoding="utf-8")
        return [png, svg]


def _point_labels(canvas: Canvas, scene: str, metadata: dict) -> None:
    points = metadata.get("screen_points", {})
    offset = 13 * canvas.scale
    labels = (("p", "p⁺"), ("e", "e⁻"), ("r_mid", "rₙ"))
    for key, label in labels:
        if key in points:
            x, y = points[key]
            canvas.text((x + offset, y - offset), label, 30)
    if scene == "vectors":
        if "v_tip" in points:
            x, y = points["v_tip"]
            canvas.text((x + offset, y - offset), "v", 32, TEAL)
        if "f_tip" in points:
            x, y = points["f_tip"]
            canvas.text((x + offset, y - offset), "F", 32, RUST)


def _panel_labels(canvas: Canvas, metadata: dict) -> None:
    for entry in metadata.get("panel_labels", []):
        if isinstance(entry, dict):
            text = entry.get("text", f"n = {entry.get('n', 1)}")
            x = entry["x"]
            y = entry["y"]
        else:
            n, x, y = entry
            text = f"n = {n}"
        canvas.text((x, y), text, 29, anchor="middle")


def _energy_panel(canvas: Canvas, n: int, finite_mass: bool, rect: tuple) -> None:
    x0, y0, x1, y1 = rect
    width = x1 - x0
    height = y1 - y0
    state = BohrState(n=n, finite_mass=finite_mass)
    first = BohrState(n=1, finite_mass=finite_mass)
    energy = state.energy_ev
    canvas.text((x0, y0), "E / eV", 28)
    baseline = y0 + 0.25 * height
    factor = 0.25 * height / (-2 * first.energy_ev)
    canvas.line((x0 + 0.04 * width, baseline), (x1 - 0.04 * width, baseline), MUTED, 1)
    bars = (("T", -energy, TEAL), ("V", 2 * energy, RUST), ("E", energy, GOLD))
    for index, (label, value, color) in enumerate(bars):
        center = x0 + width * (0.18 + index * 0.32)
        other = baseline - value * factor
        canvas.rectangle(
            (
                center - 0.065 * width,
                min(baseline, other),
                center + 0.065 * width,
                max(baseline, other),
            ),
            color,
        )
        canvas.text((center, y0 + 0.05 * height), label, 27, anchor="middle")
        canvas.text((center, y0 + 0.52 * height), _number(value), 24, anchor="middle")
    level_top = y0 + height * 0.66
    level_bottom = y1 - 18 * canvas.scale
    canvas.line((x0 + 0.13 * width, level_top), (x1 - 0.12 * width, level_top), MUTED, 1, True)
    canvas.text((x0 + 0.08 * width, level_top - 8 * canvas.scale), "0", 20, anchor="end")
    levels = sorted({1, 2, 3, n}, reverse=True)
    previous_label_y = level_top
    for level in levels:
        value = first.energy_ev / (level * level)
        y = level_top + (value / first.energy_ev) * (level_bottom - level_top)
        label_y = max(y, previous_label_y + 25 * canvas.scale)
        previous_label_y = label_y
        color = GOLD if level == n else MUTED
        canvas.line((x0 + 0.13 * width, y), (x1 - 0.12 * width, y), color, 3 if level == n else 1)
        canvas.line((x0 + 0.13 * width, y), (x0 + 0.11 * width, label_y), color, 1)
        canvas.line((x1 - 0.12 * width, y), (x1 - 0.09 * width, label_y), color, 1)
        canvas.text(
            (x0 + 0.08 * width, label_y - 8 * canvas.scale), _number(value, 3), 20, color, "end"
        )
        canvas.text((x1 - 0.07 * width, label_y - 8 * canvas.scale), f"n={level}", 20, color)


def _spectral_color(wavelength_nm: float) -> str:
    if wavelength_nm < 380:
        return MUTED
    if wavelength_nm >= 600:
        return "#B75136"
    if wavelength_nm >= 470:
        return "#378A91"
    if wavelength_nm >= 425:
        return "#5963AA"
    return "#79549D"


def _spectrum_panel(canvas: Canvas, finite_mass: bool, metadata: dict, rect: tuple) -> None:
    x0, y0, x1, y1 = rect
    width = x1 - x0
    height = y1 - y0
    initial = int(metadata.get("transition_initial", 3))
    final = int(metadata.get("transition_final", 2))
    progress = max(0.0, min(1.0, float(metadata.get("transition_progress", 1))))
    result = transition(initial, final, finite_mass=finite_mass)
    reference = BohrState(n=final, finite_mass=finite_mass).energy_ev
    top = y0 + 0.1 * height
    bottom = y0 + 0.65 * height
    canvas.text((x0, y0), "E / eV", 26)
    first_y = bottom
    last_y = bottom
    levels = sorted({final, 3, 4, 5, 6, initial}, reverse=True)
    previous_label_y = top - 25 * canvas.scale
    for level in levels:
        if level < final:
            continue
        energy = BohrState(n=level, finite_mass=finite_mass).energy_ev
        y = top + (energy / reference) * (bottom - top)
        color = GOLD if level in (initial, final) else MUTED
        canvas.line((x0 + 0.06 * width, y), (x0 + 0.70 * width, y), color, 2)
        # Quantitative energy positions stay intact; leader labels may be spaced apart.
        label_y = max(y, previous_label_y + 25 * canvas.scale)
        previous_label_y = label_y
        canvas.line((x0 + 0.70 * width, y), (x0 + 0.77 * width, label_y), color, 1)
        canvas.text((x0 + 0.80 * width, label_y - 8 * canvas.scale), f"n={level}", 21, color)
        if level == initial:
            first_y = y
        if level == final:
            last_y = y
    arrow_x = x0 + 0.38 * width
    canvas.arrow((arrow_x, first_y), (arrow_x, first_y + progress * (last_y - first_y)), GOLD, 3)
    canvas.text(
        (x0 + width / 2, y0 + 0.73 * height),
        f"λ = {_number(result.wavelength_nm, 1)} nm · Vakuum",
        26,
        anchor="middle",
    )
    line_y = y0 + 0.91 * height
    canvas.line((x0 + 0.05 * width, line_y), (x1 - 0.05 * width, line_y), MUTED, 1)
    spectral_levels = sorted({3, 4, 5, 6, initial})
    for upper in spectral_levels:
        wavelength = transition(upper, 2, finite_mass=finite_mass).wavelength_nm
        x = x0 + width * (0.05 + 0.90 * (wavelength - 360) / 360)
        canvas.line(
            (x, line_y),
            (x, line_y - 0.09 * height),
            _spectral_color(wavelength),
            3 if upper == initial else 1.5,
        )
    canvas.text((x0 + 0.05 * width, line_y + 12 * canvas.scale), "360", 18)
    canvas.text((x1 - 0.05 * width, line_y + 12 * canvas.scale), "720 nm", 18, anchor="end")


def draw_overlay(
    image: Image.Image,
    scene: str,
    n: int,
    finite_mass: bool,
    seconds: float,
    duration: float,
    metadata: dict,
) -> Image.Image:
    """Annotate a rendered RGB frame; all locations supplied by the renderer use pixels.

    This function returns a new image and never mutates the renderer's source frame.
    ``seconds`` and ``duration`` are accepted for a uniform export interface.  Physical
    event timing is supplied explicitly in metadata, rather than inferred here.
    """
    del seconds, duration
    result = image.convert("RGB").copy()
    canvas = Canvas(*result.size, image=result)
    width, height = result.size
    margin = width * 0.035
    canvas.text((margin, height * 0.055), "H", 44)
    if scene not in ("comparison", "orbital"):
        state_label = f"n = {n}"
        progress = float(metadata.get("transition_progress", 0))
        if scene == "spectrum" and 0 < progress < 1:
            initial = int(metadata.get("transition_initial", 3))
            final = int(metadata.get("transition_final", 2))
            state_label = f"{initial} → {final}"
        canvas.text((width - margin, height * 0.055), state_label, 37, anchor="end")
    time_scale = metadata.get("time_scale_s_per_video_s")
    if time_scale is not None:
        fs = float(time_scale) * 1.0e15
        time_label = f"1 s Video = {_number(fs, 4)} fs"
        if scene == "spectrum":
            time_label = f"Bahnbewegung: 1 s = {_number(fs, 4)} fs"
        canvas.text((margin, height * 0.113), time_label, 20, MUTED)
    if scene == "orbital":
        canvas.text((width - margin, height * 0.055), "Punkte: Stichprobe aus |ψ|²", 24, INK, "end")
        canvas.text((width - margin, height * 0.113), "Gemeinsame Längenskala", 21, MUTED, "end")
    _point_labels(canvas, scene, metadata)
    _panel_labels(canvas, metadata)
    panel = metadata.get("panel_rect", (0.59 * width, 0.22 * height, 0.94 * width, 0.78 * height))
    if scene == "energy":
        _energy_panel(canvas, n, finite_mass, panel)
    elif scene == "spectrum":
        _spectrum_panel(canvas, finite_mass, metadata, panel)
    elif scene == "quantization":
        scale = "aμ" if finite_mass else "a₀"
        canvas.text((width / 2, height * 0.855), f"L = nℏ     rₙ = {scale} n²", 32, anchor="middle")
    elif scene == "comparison":
        canvas.text((width / 2, height * 0.855), "rₙ ∝ n²     τₙ ∝ n³", 30, anchor="middle")
    footer = "Bohrsches Modell" if scene != "orbital" else "Bohr  ·  Schrödinger"
    if scene == "spectrum":
        footer = "Bohrsches Modell · Übergang schematisch"
    elif scene == "vectors":
        footer = "Bohrsches Modell · Pfeillängen normiert"
    canvas.text((margin, height * 0.94), footer, 24)
    canvas.text((width - margin, height * 0.94), "Größen schematisch", 21, MUTED, "end")
    return result


class Axes:
    """Explicit linear axes.  Data outside the declared domain are clipped, not scaled."""

    def __init__(self, canvas: Canvas, x_range: tuple, y_range: tuple) -> None:
        self.canvas = canvas
        self.x_min, self.x_max = x_range
        self.y_min, self.y_max = y_range
        self.left = 0.14 * canvas.width
        self.right = 0.93 * canvas.width
        self.top = 0.23 * canvas.height
        self.bottom = 0.81 * canvas.height

    def point(self, x: float, y: float) -> tuple[float, float]:
        px = self.left + (x - self.x_min) / (self.x_max - self.x_min) * (self.right - self.left)
        py = self.bottom - (y - self.y_min) / (self.y_max - self.y_min) * (self.bottom - self.top)
        return px, py

    def grid(self, xticks: tuple, yticks: tuple, xlabel: str, ylabel: str) -> None:
        canvas = self.canvas
        for value in xticks:
            x, _ = self.point(value, self.y_min)
            canvas.line((x, self.top), (x, self.bottom), GRID, 0.8)
            canvas.text((x, self.bottom + 17 * canvas.scale), _number(value), 25, anchor="middle")
        for value in yticks:
            _, y = self.point(self.x_min, value)
            canvas.line((self.left, y), (self.right, y), GRID, 0.8)
            canvas.text(
                (self.left - 20 * canvas.scale, y - 10 * canvas.scale),
                _number(value),
                25,
                anchor="end",
            )
        canvas.line((self.left, self.top), (self.left, self.bottom), INK, 1.5)
        canvas.line((self.left, self.bottom), (self.right, self.bottom), INK, 1.5)
        canvas.text(
            ((self.left + self.right) / 2, self.bottom + 66 * canvas.scale),
            xlabel,
            31,
            anchor="middle",
        )
        canvas.text((self.left, self.top - 43 * canvas.scale), ylabel, 30)

    def curve(
        self, function: Callable[[float], float], color: str = GOLD, width: float = 3.5
    ) -> None:
        points: list[tuple[float, float]] = []
        for index in range(801):
            x = self.x_min + (self.x_max - self.x_min) * index / 800
            y = function(x)
            if math.isfinite(y) and self.y_min <= y <= self.y_max:
                points.append(self.point(x, y))
            else:
                self.canvas.polyline(points, color, width)
                points = []
        self.canvas.polyline(points, color, width)


def _plot_title(canvas: Canvas, title: str, subtitle: str, finite_mass: bool) -> None:
    canvas.text((0.065 * canvas.width, 0.060 * canvas.height), title, 49)
    canvas.text((0.065 * canvas.width, 0.125 * canvas.height), subtitle, 27, MUTED)
    mass = "μ = mₑmₚ / (mₑ + mₚ)" if finite_mass else "μ = mₑ · feststehendes Proton"
    canvas.text((0.065 * canvas.width, 0.956 * canvas.height), mass, 21, MUTED)
    canvas.text(
        (0.935 * canvas.width, 0.956 * canvas.height),
        "Wasserstoff · nichtrelativistisches Coulombmodell",
        21,
        MUTED,
        "end",
    )


def _effective_potential(canvas: Canvas, finite_mass: bool) -> None:
    state = BohrState(n=1, finite_mass=finite_mass)
    energy_scale = -2 * state.energy_ev
    _plot_title(
        canvas,
        "Das Minimum bei festem Drehimpuls",
        "L = ℏ     Veff(r) = L² / (2μr²) − κ / r",
        finite_mass,
    )
    axes = Axes(canvas, (0.25, 6), (-18, 60))
    axes.grid(
        (1, 2, 3, 4, 5, 6), (-13.6, 0, 20, 40, 60), "r / aμ" if finite_mass else "r / a₀", "E / eV"
    )
    axes.curve(lambda x: energy_scale * (0.5 / (x * x) - 1 / x), GOLD)
    axes.curve(lambda x: energy_scale * 0.5 / (x * x), TEAL, 2)
    axes.curve(lambda x: -energy_scale / x, RUST, 2)
    point = axes.point(1, state.energy_ev)
    canvas.dot(point, 6)
    canvas.text(
        (point[0] + 22 * canvas.scale, point[1] - 22 * canvas.scale),
        "r = aμ" if finite_mass else "r = a₀",
        27,
    )
    canvas.text(axes.point(3.6, 47), "L² / (2μr²)", 28, TEAL)
    canvas.text(axes.point(3.6, 36), "Veff", 28, GOLD)
    canvas.text(axes.point(3.6, 25), "−κ / r", 28, RUST)


def _energy_levels(canvas: Canvas, finite_mass: bool) -> None:
    first = BohrState(n=1, finite_mass=finite_mass)
    _plot_title(
        canvas, "Diskrete Energieniveaus", "Eₙ = E₁ / n²     E = 0: Ionisationsgrenze", finite_mass
    )
    axes = Axes(canvas, (0.7, 6.3), (-15, 1))
    axes.grid((1, 2, 3, 4, 5, 6), (-15, -10, -5, 0), "n", "Eₙ / eV")
    canvas.line(axes.point(0.7, 0), axes.point(6.3, 0), MUTED, 1.5, True)
    for n in range(1, 7):
        energy = first.energy_ev / (n * n)
        canvas.line(axes.point(n - 0.22, energy), axes.point(n + 0.22, energy), GOLD, 4)
        x, y = axes.point(n, energy)
        canvas.text((x, y + 20 * canvas.scale), f"{_number(energy, 3)} eV", 23, anchor="middle")


def _radius_ratios(canvas: Canvas, finite_mass: bool) -> None:
    _plot_title(
        canvas,
        "Die erlaubten Bahnradien",
        "rₙ / aμ = n²" if finite_mass else "rₙ / a₀ = n²",
        finite_mass,
    )
    axes = Axes(canvas, (0.5, 6.5), (0, 40))
    axes.grid((1, 2, 3, 4, 5, 6), (0, 10, 20, 30, 40), "n", "rₙ / aμ" if finite_mass else "rₙ / a₀")
    for n in range(1, 7):
        point = axes.point(n, n * n)
        canvas.line(axes.point(n, 0), point, GRID, 2)
        canvas.dot(point, 7)
        canvas.text((point[0], point[1] - 36 * canvas.scale), str(n * n), 26, anchor="middle")


def _period_ratios(canvas: Canvas, finite_mass: bool) -> None:
    _plot_title(
        canvas,
        "Die Umlaufzeiten",
        "τₙ / τ₁ = n³     gleicher physikalischer Zeitmaßstab",
        finite_mass,
    )
    axes = Axes(canvas, (0.5, 6.5), (0, 240))
    axes.grid((1, 2, 3, 4, 5, 6), (0, 60, 120, 180, 240), "n", "τₙ / τ₁")
    for n in range(1, 7):
        value = n * n * n
        point = axes.point(n, value)
        canvas.line(axes.point(n, 0), point, GRID, 2)
        canvas.dot(point, 7)
        canvas.text((point[0], point[1] - 36 * canvas.scale), str(value), 26, anchor="middle")


def _balmer_lines(canvas: Canvas, finite_mass: bool) -> None:
    _plot_title(
        canvas,
        "Die Balmer-Serie",
        "n → 2     Eγ = Eₙ − E₂ = hc / λ     Linienpositionen, keine Intensitäten",
        finite_mass,
    )
    left = 0.14 * canvas.width
    right = 0.93 * canvas.width
    top = 0.30 * canvas.height
    bottom = 0.76 * canvas.height
    for wavelength in (380, 400, 450, 500, 550, 600, 650, 700):
        x = left + (wavelength - 380) / 340 * (right - left)
        canvas.line((x, bottom), (x, bottom + 10 * canvas.scale), INK, 1.5)
        canvas.text((x, bottom + 24 * canvas.scale), str(wavelength), 25, anchor="middle")
    canvas.line((left, bottom), (right, bottom), INK, 1.5)
    for n in (3, 4, 5, 6):
        wavelength = transition(n, 2, finite_mass=finite_mass).wavelength_nm
        x = left + (wavelength - 380) / 340 * (right - left)
        color = _spectral_color(wavelength)
        canvas.line((x, top), (x, bottom), color, 4)
        label_y = top - (54 if n % 2 == 0 else 102) * canvas.scale
        canvas.text((x, label_y), f"{n} → 2", 28, color, "middle")
        canvas.text(
            (x, label_y + 34 * canvas.scale), f"{_number(wavelength, 2)} nm", 23, color, "middle"
        )
    canvas.text(
        ((left + right) / 2, bottom + 86 * canvas.scale),
        "Vakuumwellenlänge λ / nm",
        31,
        anchor="middle",
    )


def _radial_probability(canvas: Canvas, finite_mass: bool) -> None:
    _plot_title(
        canvas,
        "Ein Radius – eine Verteilung",
        "Bohr: r = aμ     Schrödinger 1s: aμ P(r) = 4x² exp(−2x),  x = r/aμ"
        if finite_mass
        else "Bohr: r = a₀     Schrödinger 1s: a₀ P(r) = 4x² exp(−2x),  x = r/a₀",
        finite_mass,
    )
    axes = Axes(canvas, (0, 7), (0, 0.65))
    axes.grid(
        (0, 1, 2, 3, 4, 5, 6, 7),
        (0, 0.2, 0.4, 0.6),
        "r / aμ" if finite_mass else "r / a₀",
        "aμ P(r)" if finite_mass else "a₀ P(r)",
    )
    axes.curve(lambda x: 4 * x * x * math.exp(-2 * x), GOLD, 4)
    canvas.line(axes.point(1, 0), axes.point(1, 0.62), TEAL, 2, True)
    canvas.line(axes.point(1.5, 0), axes.point(1.5, 0.39), MUTED, 1.5, True)
    canvas.text(axes.point(2.7, 0.54), "1s · radiale Wahrscheinlichkeitsdichte", 28, GOLD)
    canvas.text(
        axes.point(2.7, 0.45),
        "Bohr: fester Abstand bei r/aμ = 1" if finite_mass else "Bohr: fester Abstand bei r/a₀ = 1",
        26,
        TEAL,
    )
    canvas.text(
        axes.point(2.7, 0.36), "⟨r⟩₁ₛ = 1,5 aμ" if finite_mass else "⟨r⟩₁ₛ = 1,5 a₀", 26, MUTED
    )
    canvas.text(
        axes.point(2.7, 0.27),
        "Die gestrichelte Bohr-Markierung ist keine endliche Dichte.",
        21,
        MUTED,
    )


def export_plots(
    output: Path, finite_mass: bool = True, width: int = 3840, height: int = 2160
) -> list[Path]:
    """Export six independently usable scientific figures as PNG and standalone SVG."""
    if width < 640 or height < 360:
        raise ValueError("Plots need at least 640 × 360 pixels.")
    plots = (
        ("01_effektives_potential", _effective_potential),
        ("02_energieniveaus", _energy_levels),
        ("03_bahnradien", _radius_ratios),
        ("04_umlaufzeiten", _period_ratios),
        ("05_balmerlinien", _balmer_lines),
        ("06_radialwahrscheinlichkeit", _radial_probability),
    )
    written: list[Path] = []
    for filename, build in plots:
        canvas = Canvas(width, height)
        build(canvas, finite_mass)
        written.extend(canvas.save(Path(output) / filename))
    return written
