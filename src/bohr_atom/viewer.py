"""Small GLFW viewer using the same scene renderer as image and video export."""

import time
from typing import Any

import glfw
import moderngl
from PIL import Image

from bohr_atom import config
from bohr_atom.camera import camera_pose
from bohr_atom.export import default_scene_n, validate_render, validate_scene
from bohr_atom.renderer import BohrRenderer, RenderSettings


class BohrViewer:
    def __init__(
        self,
        settings: RenderSettings,
        scene: str = "orbit",
        n: int | None = None,
        duration: float = 36.0,
        test_frames: int = 0,
    ) -> None:
        n = default_scene_n(scene) if n is None else n
        validate_scene(scene, n, duration)
        validate_render(settings, 1)
        if type(test_frames) is not int or test_frames < 0:
            raise ValueError("Test frame count must be a nonnegative integer.")
        self.settings = settings
        self.scene = scene
        self.n = n
        self.duration = duration
        self.test_frames = test_frames
        self.seconds = 0.0
        self.paused = False
        self.azimuth: float | None = None
        self.elevation: float | None = None
        self.dragging = False
        self.last_cursor = (0.0, 0.0)
        self.window: Any = None
        self.context: moderngl.Context | None = None
        self.renderer: BohrRenderer | None = None
        self.display_texture: Any = None
        self.display_buffer: Any = None

    def on_key(self, window: Any, key: int, scancode: int, action: int, modifiers: int) -> None:
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_SPACE:
            self.paused = not self.paused
        elif key == glfw.KEY_TAB:
            current = config.SCENES.index(self.scene)
            step = -1 if modifiers & glfw.MOD_SHIFT else 1
            self.scene = config.SCENES[(current + step) % len(config.SCENES)]
            if self.scene == "spectrum" and self.n < 3:
                self.n = 3
            self.seconds = 0.0
        elif key == glfw.KEY_R:
            self.seconds = 0.0
            self.azimuth = None
            self.elevation = None
        elif glfw.KEY_1 <= key <= glfw.KEY_6:
            chosen_n = key - glfw.KEY_1 + 1
            if self.scene == "spectrum" and chosen_n < 3:
                return
            self.n = chosen_n
            self.seconds = 0.0

    def on_mouse_button(self, window: Any, button: int, action: int, modifiers: int) -> None:
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.dragging = action == glfw.PRESS
            self.last_cursor = glfw.get_cursor_pos(window)

    def on_cursor(self, window: Any, x: float, y: float) -> None:
        if self.dragging:
            automatic_azimuth, automatic_elevation = camera_pose(self.seconds, self.duration)
            azimuth = automatic_azimuth if self.azimuth is None else self.azimuth
            elevation = automatic_elevation if self.elevation is None else self.elevation
            self.azimuth = azimuth - 0.25 * (x - self.last_cursor[0])
            self.elevation = min(85.0, max(5.0, elevation + 0.25 * (y - self.last_cursor[1])))
        self.last_cursor = (x, y)

    def render_frame(self, elapsed: float) -> None:
        if self.renderer is None or self.context is None or self.display_texture is None:
            raise RuntimeError("Viewer has no active renderer.")
        if not self.paused:
            self.seconds = (self.seconds + elapsed) % self.duration
        image = self.renderer.render(
            self.scene,
            self.seconds,
            self.duration,
            n=self.n,
            azimuth=self.azimuth,
            elevation=self.elevation,
        )
        try:
            flipped = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            try:
                self.display_texture.write(flipped.tobytes())
            finally:
                flipped.close()
        finally:
            image.close()
        self.context.copy_framebuffer(self.context.screen, self.display_buffer)

    def draw_loop(self) -> None:
        previous = time.perf_counter()
        frames = 0
        while not glfw.window_should_close(self.window):
            current = time.perf_counter()
            elapsed = min(0.1, max(0.0, current - previous))
            previous = current
            glfw.poll_events()
            self.render_frame(elapsed)
            glfw.swap_buffers(self.window)
            frames += 1
            if self.test_frames and frames >= self.test_frames:
                glfw.set_window_should_close(self.window, True)

    def close(self) -> None:
        try:
            if self.display_buffer is not None:
                self.display_buffer.release()
            if self.display_texture is not None:
                self.display_texture.release()
            if self.renderer is not None:
                self.renderer.close()
        finally:
            if self.context is not None:
                self.context.release()
            if self.window is not None:
                glfw.destroy_window(self.window)
            glfw.terminate()

    def run(self) -> None:
        if not glfw.init():
            raise RuntimeError("GLFW could not initialize; a desktop with OpenGL 3.3 is required.")
        try:
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
            glfw.window_hint(glfw.RESIZABLE, glfw.FALSE)
            if self.test_frames:
                glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
            title = "Bohr | Drag: camera | Space: pause | Tab: scene | 1-6: n | R: reset"
            self.window = glfw.create_window(
                self.settings.width, self.settings.height, title, None, None
            )
            if not self.window:
                raise RuntimeError("An OpenGL 3.3 window could not be created.")
            glfw.make_context_current(self.window)
            glfw.swap_interval(1)
            self.context = moderngl.create_context(require=330)
            self.renderer = BohrRenderer(self.context, self.settings)
            self.display_texture = self.context.texture(
                (self.settings.width, self.settings.height), components=3
            )
            self.display_buffer = self.context.framebuffer(color_attachments=[self.display_texture])
            glfw.set_key_callback(self.window, self.on_key)
            glfw.set_mouse_button_callback(self.window, self.on_mouse_button)
            glfw.set_cursor_pos_callback(self.window, self.on_cursor)
            self.draw_loop()
        finally:
            self.close()
