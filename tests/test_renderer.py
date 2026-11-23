"""CPU-only statistical checks for the renderer's stationary 1s probability samples."""

import math
import unittest
from unittest.mock import patch

import numpy as np

from bohr_atom import config
from bohr_atom.renderer import BohrRenderer

SAMPLE_COUNT = 90_000
SIGMA_MARGIN = 5.0


class DensitySamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Calling this static method never constructs a renderer or a GPU context.
        with patch.object(config, "DENSITY_SAMPLES", SAMPLE_COUNT):
            with patch.object(config, "DENSITY_SEED", 7):
                cls.samples = BohrRenderer._density_samples()
        cls.positions = cls.samples.astype(np.float64)
        cls.radii = np.linalg.norm(cls.positions, axis=1)
        cls.directions = cls.positions / cls.radii[:, None]

    def assert_mean(self, observations: np.ndarray, expectation: float, variance: float) -> None:
        # Five analytic standard errors: finite Monte Carlo sampling is not exact.
        tolerance = SIGMA_MARGIN * math.sqrt(variance / len(observations))
        self.assertLessEqual(abs(float(np.mean(observations)) - expectation), tolerance)

    def test_seeded_reproducibility_without_gpu_initialization(self) -> None:
        with patch.object(config, "DENSITY_SAMPLES", SAMPLE_COUNT):
            with patch.object(config, "DENSITY_SEED", 7):
                repeated = BohrRenderer._density_samples()
        self.assertEqual(repeated.shape, (SAMPLE_COUNT, 3))
        self.assertEqual(repeated.dtype, np.dtype("float32"))
        np.testing.assert_array_equal(repeated, self.samples)

    def test_radial_first_moment(self) -> None:
        # P(r)=4*r^2*exp(-2*r): E[r]=3/2, Var(r)=3/4 in a_mu units.
        self.assert_mean(self.radii, 1.5, 0.75)

    def test_radial_second_moment(self) -> None:
        # E[r^2]=3 and E[r^4]=45/2, hence Var(r^2)=27/2.
        self.assert_mean(self.radii * self.radii, 3.0, 13.5)

    def test_isotropic_direction_moments(self) -> None:
        for component in range(3):
            direction = self.directions[:, component]
            self.assert_mean(direction, 0.0, 1.0 / 3.0)
            # A Cartesian component of a uniform unit vector is Uniform[-1,1].
            self.assert_mean(direction * direction, 1.0 / 3.0, 4.0 / 45.0)
        self.assert_mean(self.directions[:, 0] * self.directions[:, 1], 0.0, 1.0 / 15.0)
        self.assert_mean(self.directions[:, 0] * self.directions[:, 2], 0.0, 1.0 / 15.0)
        self.assert_mean(self.directions[:, 1] * self.directions[:, 2], 0.0, 1.0 / 15.0)

    def test_isotropic_solid_angle_sectors(self) -> None:
        # Each azimuth quarter combined with either hemisphere has solid angle 4*pi/8.
        # This also checks polar/azimuth independence, rather than only covariance.
        azimuth = np.mod(np.arctan2(self.positions[:, 1], self.positions[:, 0]), math.tau)
        sectors = np.floor(azimuth / (math.pi / 2.0)).astype(np.int32)
        sectors += 4 * (self.positions[:, 2] >= 0.0).astype(np.int32)
        counts = np.bincount(sectors, minlength=8)
        probability = 1.0 / 8.0
        expected_count = SAMPLE_COUNT * probability
        tolerance = SIGMA_MARGIN * math.sqrt(SAMPLE_COUNT * probability * (1.0 - probability))
        self.assertLessEqual(float(np.max(np.abs(counts - expected_count))), tolerance)


if __name__ == "__main__":
    unittest.main()
