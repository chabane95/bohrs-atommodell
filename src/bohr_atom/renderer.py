"""A small GPU renderer. Physics is calculated in SI; display choices stay here."""

import math
from dataclasses import dataclass

import moderngl
import numpy as np
from PIL import Image

from bohr_atom import config, shaders
from bohr_atom.camera import camera_pose, orthographic, screen_point, smoothstep, view_matrix
from bohr_atom.physics import BohrState, state_at_time, transition
from bohr_atom.presentation import draw_overlay


@dataclass(frozen=True)
class RenderSettings:
    width: int = config.WIDTH
    height: int = config.HEIGHT
    labels: bool = True
    finite_mass: bool = True


class BohrRenderer:
    """Seven deliberately composed scenes sharing one deterministic physical clock."""

    def __init__(self, context: moderngl.Context, settings: RenderSettings) -> None:
        if type(settings.width) is not int or type(settings.height) is not int:
            raise TypeError("Image dimensions must be integers.")
        if settings.width < 1 or settings.height < 1:
            raise ValueError("Image dimensions must be positive.")
        BohrState(1, settings.finite_mass)
        self.context = context
        self.settings = settings
        self.metadata: dict = {}
        self.color = context.texture((settings.width, settings.height), 3)
        self.depth = context.depth_renderbuffer((settings.width, settings.height))
        self.framebuffer = context.framebuffer([self.color], self.depth)
        self.background_program = context.program(
            vertex_shader=shaders.SCREEN_VERTEX, fragment_shader=shaders.BACKGROUND_FRAGMENT
        )
        self.background = context.vertex_array(self.background_program, [])
        self.sphere_program = context.program(
            vertex_shader=shaders.SPHERE_VERTEX, fragment_shader=shaders.SPHERE_FRAGMENT
        )
        self.line_program = context.program(
            vertex_shader=shaders.LINE_VERTEX, fragment_shader=shaders.LINE_FRAGMENT
        )
        corners = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]], dtype="f4")
        self.corner_buffer = context.buffer(corners.tobytes())
        self.instance_buffer = context.buffer(reserve=(config.DENSITY_SAMPLES + 4) * 16)
        self.spheres = context.vertex_array(
            self.sphere_program,
            [
                (self.corner_buffer, "2f", "in_corner"),
                (self.instance_buffer, "3f 1f /i", "in_position", "in_radius"),
            ],
        )
        self.line_buffer = context.buffer(reserve=3000 * 12)
        self.lines = context.vertex_array(
            self.line_program, [(self.line_buffer, "3f", "in_position")]
        )
        angle = np.linspace(0.0, math.tau, 721, dtype="f4")
        self.circle = np.column_stack((np.cos(angle), np.sin(angle), np.zeros_like(angle)))
        self.cloud = self._density_samples()
        self.view = view_matrix(36, 25)
        self.projection = orthographic(settings.width / settings.height)
        self.closed = False

    @staticmethod
    def _density_samples() -> np.ndarray:
        """1s: P(r)dr = 4r²/a³ exp(-2r/a)dr; Gamma(3,a/2), isotropic angles.

        Coordinates are in units of a_mu. These are fixed probability samples,
        not simultaneous electrons, time samples of an orbit, or moving particles.
        """
        generator = np.random.default_rng(config.DENSITY_SEED)
        count = config.DENSITY_SAMPLES
        radius = generator.gamma(3.0, 0.5, count)
        cosine = generator.uniform(-1.0, 1.0, count)
        azimuth = generator.uniform(0.0, math.tau, count)
        sine = np.sqrt(1.0 - cosine * cosine)
        result = np.empty((count, 3), dtype="f4")
        result[:, 0] = radius * sine * np.cos(azimuth)
        result[:, 1] = radius * sine * np.sin(azimuth)
        result[:, 2] = radius * cosine
        return result

    def _set_matrices(self) -> None:
        self.sphere_program["view"].write(self.view.T.tobytes())
        self.sphere_program["projection"].write(self.projection.T.tobytes())
        self.line_program["view"].write(self.view.T.tobytes())
        self.line_program["projection"].write(self.projection.T.tobytes())

    def _center(self, horizontal: float = 0.0, vertical: float = 0.09) -> np.ndarray:
        return self.view[0, :3] * horizontal + self.view[1, :3] * vertical

    def _project(self, point) -> tuple[float, float]:
        return screen_point(
            point, self.view, self.projection, self.settings.width, self.settings.height
        )

    def _geometry(self, points: np.ndarray, color: tuple, mode=moderngl.TRIANGLES) -> None:
        vertices = np.asarray(points, dtype="f4")
        self.line_buffer.write(vertices.tobytes())
        self.line_program["line_color"].value = color
        self.lines.render(mode=mode, vertices=len(vertices))

    def _ring(
        self,
        radius: float,
        center: np.ndarray,
        color=(0.72, 0.48, 0.12, 0.62),
        width=config.ORBIT_LINE_WIDTH,
    ) -> None:
        vertices = np.empty((len(self.circle) * 2, 3), dtype="f4")
        tangent = np.column_stack(
            (-self.circle[:, 1], self.circle[:, 0], np.zeros(len(self.circle)))
        )
        side = np.cross(tangent, self.view[2, :3])
        side /= np.linalg.norm(side, axis=1, keepdims=True)
        vertices[0::2] = self.circle * radius + center - side * width / 2
        vertices[1::2] = self.circle * radius + center + side * width / 2
        self._geometry(vertices, color, moderngl.TRIANGLE_STRIP)

    def _segment(self, start, stop, color, width=0.002) -> None:
        direction = np.asarray(stop) - start
        length = float(np.linalg.norm(direction))
        if length < 1e-8:
            return
        side = np.cross(direction / length, self.view[2, :3])
        norm = float(np.linalg.norm(side))
        if norm < 1e-8:
            return
        side *= width / (2 * norm)
        vertices = np.array([start - side, start + side, stop - side, stop + side])
        self._geometry(vertices, color, moderngl.TRIANGLE_STRIP)

    def _arrow(self, start, stop, color) -> None:
        direction = np.asarray(stop) - start
        direction /= np.linalg.norm(direction)
        side = np.cross(direction, self.view[2, :3])
        side /= np.linalg.norm(side)
        base = stop - direction * 0.033
        self._segment(start, base, color, 0.0036)
        self._geometry(np.array([stop, base - side * 0.014, base + side * 0.014]), color)

    def _beads(self, positions: np.ndarray, radii, textured=True) -> None:
        instances = np.empty((len(positions), 4), dtype="f4")
        instances[:, :3] = positions
        instances[:, 3] = radii
        self.instance_buffer.write(instances.tobytes())
        self.sphere_program["microtexture"].value = textured
        self.spheres.render(mode=moderngl.TRIANGLE_STRIP, vertices=4, instances=len(positions))

    def _atom(
        self,
        state: BohrState,
        seconds: float,
        time_scale: float,
        length_scale: float,
        center: np.ndarray,
        radius_guide=False,
        vectors=False,
        bead_scale=1.0,
        electron_visible=True,
        draw_ring=True,
    ) -> tuple[np.ndarray, np.ndarray]:
        sample = state_at_time(state, seconds * time_scale, config.INITIAL_PHASE)
        electron = np.array(sample.electron) / length_scale + center
        proton = np.array(sample.proton) / length_scale + center
        if draw_ring:
            self._ring(state.electron_radius_m / length_scale, center)
        if radius_guide:
            self._segment(proton, electron, (0.38, 0.40, 0.39, 0.38), 0.0015)
        if vectors:
            self.metadata["vector_display"] = "Directions; arrow lengths independently normalized."
            tangent = np.array(sample.relative_velocity) / state.speed_m_s
            inward = -np.array(sample.relative) / state.radius_m
            v_tip = electron + tangent * 0.38
            f_tip = electron + inward * 0.34
            self._arrow(electron, v_tip, (0.20, 0.46, 0.48, 0.95))
            self._arrow(electron, f_tip, (0.65, 0.37, 0.25, 0.95))
            self.metadata["screen_points"]["v_tip"] = self._project(v_tip)
            self.metadata["screen_points"]["f_tip"] = self._project(f_tip)
        if electron_visible:
            self._beads(
                np.array([proton, electron]),
                [
                    config.PROTON_DISPLAY_RADIUS * bead_scale,
                    config.ELECTRON_DISPLAY_RADIUS * bead_scale,
                ],
            )
        else:
            self._beads(np.array([proton]), config.PROTON_DISPLAY_RADIUS * bead_scale)
        return proton, electron

    def _labels(self, proton, electron, radius=True) -> None:
        px, py = self._project(proton)
        ex, ey = self._project(electron)
        self.metadata["screen_points"]["p"] = (
            px + config.PROTON_DISPLAY_RADIUS * self.settings.height / 2,
            py,
        )
        self.metadata["screen_points"]["e"] = (
            ex + config.ELECTRON_DISPLAY_RADIUS * self.settings.height / 2,
            ey,
        )
        if math.hypot(ex - px, ey - py) < self.settings.height * 0.11:
            self.metadata["screen_points"]["p"] = (px, py - self.settings.height * 0.045)
            self.metadata["screen_points"]["e"] = (ex, ey + self.settings.height * 0.035)
        if radius:
            self.metadata["screen_points"]["r_mid"] = self._project(proton * 0.54 + electron * 0.46)

    def _single(self, state: BohrState, seconds: float, scene: str) -> None:
        length_scale = state.radius_m / 0.88
        time_scale = state.period_s / config.ORBIT_VIDEO_PERIOD
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        proton, electron = self._atom(
            state, seconds, time_scale, length_scale, self._center(), True, scene == "vectors"
        )
        self._labels(proton, electron)

    def _quantization(self, state: BohrState, seconds: float, duration: float) -> None:
        outer_n = max(4, state.n)
        length_scale = state.length_scale_m * outer_n * outer_n / 0.88
        time_scale = state.period_s / config.ORBIT_VIDEO_PERIOD
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        center = self._center()
        for level in range(1, outer_n + 1):
            other = BohrState(level, self.settings.finite_mass)
            opacity = smoothstep(seconds / duration * 5.0 - (level - 1) * 0.32)
            if level == state.n:
                opacity = 1.0
            self._ring(
                other.electron_radius_m / length_scale,
                center,
                (0.72, 0.48, 0.12, opacity * (0.78 if level == state.n else 0.26)),
            )
        proton, electron = self._atom(
            state, seconds, time_scale, length_scale, center, bead_scale=0.23, draw_ring=False
        )
        self._labels(proton, electron, False)

    def _comparison(self, seconds: float) -> None:
        first = BohrState(1, self.settings.finite_mass)
        length_scale = first.length_scale_m * 9 / 0.48
        time_scale = first.period_s / config.COMPARISON_N1_VIDEO_PERIOD
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        self.metadata["shared_time_and_length_scale"] = True
        self.metadata["panel_labels"] = []
        for level in (1, 2, 3):
            state = BohrState(level, self.settings.finite_mass)
            center = self._center((level - 2) * 1.13)
            self._atom(state, seconds, time_scale, length_scale, center, bead_scale=0.23)
            x, _ = self._project(center)
            self.metadata["panel_labels"].append(
                {"n": level, "x": x, "y": self.settings.height * 0.77}
            )

    def _energy(self, state: BohrState, seconds: float) -> None:
        length_scale = state.radius_m / 0.63
        time_scale = state.period_s / config.ORBIT_VIDEO_PERIOD
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        proton, electron = self._atom(
            state, seconds, time_scale, length_scale, self._center(-0.82), bead_scale=0.85
        )
        self._labels(proton, electron, False)

    def _spectrum(self, state: BohrState, seconds: float, duration: float) -> int:
        initial = BohrState(max(3, state.n), self.settings.finite_mass)
        final = BohrState(2, self.settings.finite_mass)
        length_scale = initial.radius_m / 0.63
        time_scale = initial.period_s / config.ORBIT_VIDEO_PERIOD
        progress = seconds / duration
        transition_progress = smoothstep((progress - 0.32) / 0.18)
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        self.metadata["transition_initial"] = initial.n
        self.metadata["transition_final"] = 2
        self.metadata["transition_progress"] = transition_progress
        self.metadata["transition_timing"] = "Schematic edit; no transition trajectory or rate."
        self.metadata["wavelength_vacuum_nm"] = transition(
            initial.n, 2, self.settings.finite_mass
        ).wavelength_nm
        center = self._center(-0.82)
        self._ring(
            initial.electron_radius_m / length_scale,
            center,
            (0.72, 0.48, 0.12, 0.45 if progress < 0.32 else 0.19),
        )
        self._ring(
            final.electron_radius_m / length_scale,
            center,
            (0.72, 0.48, 0.12, 0.60 if progress >= 0.50 else 0.19),
        )
        active = initial if progress < 0.50 else final
        electron_visible = progress < 0.32 or progress >= 0.50
        bead_scale = min(
            0.72, final.electron_radius_m / length_scale / config.PROTON_DISPLAY_RADIUS * 0.40
        )
        proton, electron = self._atom(
            active,
            seconds,
            time_scale,
            length_scale,
            center,
            bead_scale=bead_scale,
            electron_visible=electron_visible,
            draw_ring=False,
        )
        self._labels(proton, electron, False)
        if not electron_visible:
            del self.metadata["screen_points"]["e"]
        return active.n

    def _orbital(self, seconds: float) -> None:
        state = BohrState(1, self.settings.finite_mass)
        length_scale = state.length_scale_m / 0.105
        time_scale = state.period_s / config.ORBIT_VIDEO_PERIOD
        self.metadata["display_length_scale_m"] = length_scale
        self.metadata["time_scale_s_per_video_s"] = time_scale
        self.metadata["shared_length_scale"] = True
        self.metadata["density"] = "Stationary 1s probability samples; no particle trajectories."
        self.metadata["density_seed"] = config.DENSITY_SEED
        left = self._center(-0.82)
        right = self._center(0.82)
        self._atom(state, seconds, time_scale, length_scale, left, bead_scale=0.42)
        # Both panels use electron coordinates in the COM frame, with the same scale.
        # Display r <= 6a_mu (99.9478% probability); do not rescale retained samples.
        retained = self.cloud[np.linalg.norm(self.cloud, axis=1) <= 6.0]
        positions = retained * (state.electron_radius_m / length_scale) + right
        self.metadata["density_display_cutoff_a_mu"] = 6.0
        self.metadata["density_display_probability"] = 1.0 - 85.0 * math.exp(-12.0)
        self._beads(positions, 0.0019, False)
        lx, _ = self._project(left)
        rx, _ = self._project(right)
        self.metadata["panel_labels"] = [
            {"text": "Bohr · n = 1", "x": lx, "y": self.settings.height * 0.79},
            {"text": "1s · |ψ|²", "x": rx, "y": self.settings.height * 0.79},
        ]

    def render(
        self,
        scene: str,
        seconds: float,
        duration: float,
        n: int = 1,
        azimuth: float | None = None,
        elevation: float | None = None,
    ) -> Image.Image:
        if self.closed:
            raise RuntimeError("Renderer is closed.")
        if scene not in config.SCENES:
            raise ValueError(f"Unknown scene: {scene}")
        if not math.isfinite(seconds) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Time must be finite and duration positive.")
        state = BohrState(n, self.settings.finite_mass)
        az, el = camera_pose(seconds, duration)
        if azimuth is not None:
            az = float(azimuth)
        if elevation is not None:
            el = float(elevation)
        if not math.isfinite(az) or not math.isfinite(el):
            raise ValueError("Camera angles must be finite.")
        self.view = view_matrix(az, min(85.0, max(5.0, el)))
        self._set_matrices()
        self.metadata = {
            "model": "Historical Bohr hydrogen model; stationary circular states are postulates.",
            "scene": scene,
            "actual_n": n,
            "screen_points": {},
            "azimuth_degrees": az,
            "elevation_degrees": el,
            "particle_sizes": "Schematic. Orbital radii and clocks calculated from physics.py.",
        }
        self.framebuffer.use()
        self.context.viewport = (0, 0, self.settings.width, self.settings.height)
        self.framebuffer.clear(1, 1, 1, depth=1.0)
        self.context.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.background.render(mode=moderngl.TRIANGLES, vertices=3)
        self.context.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.context.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        actual_n = n
        if scene in ("orbit", "vectors"):
            self._single(state, seconds, scene)
        elif scene == "quantization":
            self._quantization(state, seconds, duration)
        elif scene == "comparison":
            self._comparison(seconds)
            actual_n = None
            self.metadata["displayed_states"] = [1, 2, 3]
        elif scene == "energy":
            self._energy(state, seconds)
        elif scene == "spectrum":
            actual_n = self._spectrum(state, seconds, duration)
        elif scene == "orbital":
            actual_n = 1
            self._orbital(seconds)
        self.metadata["actual_n"] = actual_n
        data = self.framebuffer.read(components=3, alignment=1)
        result = Image.frombytes("RGB", (self.settings.width, self.settings.height), data)
        result = result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if self.settings.labels:
            labeled = draw_overlay(
                result, scene, actual_n, self.settings.finite_mass, seconds, duration, self.metadata
            )
            result.close()
            return labeled
        return result

    def close(self) -> None:
        if self.closed:
            return
        self.spheres.release()
        self.lines.release()
        self.background.release()
        self.corner_buffer.release()
        self.instance_buffer.release()
        self.line_buffer.release()
        self.sphere_program.release()
        self.line_program.release()
        self.background_program.release()
        self.framebuffer.release()
        self.depth.release()
        self.color.release()
        self.closed = True
