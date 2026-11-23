"""Small explicit camera functions; scene length units never alter physical values."""

import math

import numpy as np


def smoothstep(value: float) -> float:
    bounded = min(1.0, max(0.0, value))
    return bounded * bounded * (3.0 - 2.0 * bounded)


def camera_pose(seconds: float, duration: float) -> tuple[float, float]:
    """Three held views, separated by two slow moves; physical time stays continuous."""
    progress = seconds / duration
    first = smoothstep((progress - 0.23) / 0.18)
    second = smoothstep((progress - 0.64) / 0.18)
    return 36.0 + 22.0 * first - 14.0 * second, 25.0 + 12.0 * first + 23.0 * second


def view_matrix(azimuth: float, elevation: float) -> np.ndarray:
    az = math.radians(azimuth)
    el = math.radians(elevation)
    eye = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    forward = -eye
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    matrix = np.eye(4, dtype=np.float32)
    matrix[0, :3] = right
    matrix[1, :3] = up
    matrix[2, :3] = -forward
    matrix[2, 3] = -6.0
    return matrix


def orthographic(aspect: float, half_height: float = 1.0) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float32)
    matrix[0, 0] = 1.0 / (half_height * aspect)
    matrix[1, 1] = 1.0 / half_height
    matrix[2, 2] = -2.0 / 20.0
    matrix[2, 3] = -1.0
    return matrix


def screen_point(position, view, projection, width: int, height: int) -> tuple[float, float]:
    vector = np.array([position[0], position[1], position[2], 1.0])
    clip = projection @ view @ vector
    return (
        float((clip[0] / clip[3] + 1.0) * width * 0.5),
        float((1.0 - clip[1] / clip[3]) * height * 0.5),
    )
