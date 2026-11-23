"""Explicit production settings: edit these constants directly."""

WIDTH = 1920
HEIGHT = 1080
FPS = 30
SUPERSAMPLE = 2
CLIP_SECONDS = 36.0
DEFAULT_N = 1
FINITE_MASS = True

# One full revolution lasts this many video seconds in single-state scenes.
# Comparisons deliberately use one shared physical time scale instead.
ORBIT_VIDEO_PERIOD = 8.0
COMPARISON_N1_VIDEO_PERIOD = 1.5
INITIAL_PHASE = -0.70
PROTON_DISPLAY_RADIUS = 0.080
ELECTRON_DISPLAY_RADIUS = 0.030
ORBIT_LINE_WIDTH = 0.0032
DENSITY_SAMPLES = 90_000
DENSITY_SEED = 7

SCENES = ("orbit", "vectors", "quantization", "comparison", "energy", "spectrum", "orbital")
