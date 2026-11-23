"""Independent equations, derivatives and conservation checks for the Bohr core."""

import dataclasses
import math
import unittest

from bohr_atom.physics import (
    A0,
    E_CHARGE,
    ELECTRON_MASS,
    HBAR,
    KAPPA,
    PROTON_MASS,
    BohrState,
    C,
    H,
    classical_radius,
    effective_potential,
    state_at_time,
    transition,
)


def magnitude(vector: tuple[float, float, float]) -> float:
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


class RelativeAssertions(unittest.TestCase):
    def assertRelative(self, actual: float, expected: float, tolerance: float = 2.0e-14) -> None:
        self.assertLessEqual(abs(actual - expected), tolerance * abs(expected))


class StateTests(RelativeAssertions):
    def test_invalid_quantum_numbers_and_mass_flags(self) -> None:
        for value in (0, -1, 13):
            with self.assertRaises(ValueError):
                BohrState(value)
        for value in (True, False, 1.0, "1", None):
            with self.assertRaises(TypeError):
                BohrState(value)
        for value in (0, 1, "yes", None):
            with self.assertRaises(TypeError):
                BohrState(1, value)

    def test_state_is_immutable(self) -> None:
        state = BohrState()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            state.n = 2

    def test_ground_state_matches_independent_codata_scales(self) -> None:
        fixed = BohrState(1, False)
        self.assertRelative(A0, 5.29177210544e-11, 5.0e-10)
        self.assertRelative(fixed.energy_ev, -13.60569312299, 5.0e-10)
        self.assertRelative(fixed.speed_m_s, 2.18769126216e6, 5.0e-10)
        self.assertRelative(fixed.period_s, 1.51982984606e-16, 5.0e-10)

    def test_quantization_and_coulomb_force_for_every_supported_n(self) -> None:
        for quantum_number in range(1, 13):
            state = BohrState(quantum_number)
            inertial_force = state.reduced_mass_kg * state.speed_m_s**2 / state.radius_m
            electric_force = KAPPA / state.radius_m**2
            self.assertRelative(inertial_force, electric_force)
            measured_momentum = state.reduced_mass_kg * state.radius_m * state.speed_m_s
            self.assertRelative(measured_momentum, quantum_number * HBAR)

    def test_n_scaling_of_all_observables(self) -> None:
        ground = BohrState(1)
        for quantum_number in range(1, 13):
            state = BohrState(quantum_number)
            self.assertRelative(state.radius_m / ground.radius_m, quantum_number**2)
            self.assertRelative(state.speed_m_s / ground.speed_m_s, 1.0 / quantum_number)
            self.assertRelative(state.period_s / ground.period_s, quantum_number**3)
            self.assertRelative(state.energy_j / ground.energy_j, 1.0 / quantum_number**2)

    def test_energy_relations_and_ev_conversion(self) -> None:
        state = BohrState(7)
        self.assertRelative(state.energy_j, state.kinetic_j + state.potential_j)
        self.assertRelative(state.kinetic_j, -state.energy_j)
        self.assertRelative(state.potential_j, 2.0 * state.energy_j)
        self.assertRelative(state.energy_ev * E_CHARGE, state.energy_j)

    def test_finite_mass_correction_and_individual_radii(self) -> None:
        finite = BohrState(4, True)
        fixed = BohrState(4, False)
        ratio = 1.0 + ELECTRON_MASS / PROTON_MASS
        self.assertRelative(finite.radius_m / fixed.radius_m, ratio)
        self.assertRelative(finite.period_s / fixed.period_s, ratio)
        self.assertRelative(finite.energy_j / fixed.energy_j, 1.0 / ratio)
        self.assertRelative(finite.speed_m_s, fixed.speed_m_s)
        self.assertRelative(finite.electron_radius_m, fixed.radius_m)
        self.assertRelative(finite.electron_radius_m + finite.proton_radius_m, finite.radius_m)
        self.assertEqual(fixed.proton_radius_m, 0.0)


class OrbitTests(RelativeAssertions):
    def test_known_initial_and_quarter_turn_positions(self) -> None:
        state = BohrState(3)
        initial = state_at_time(state, 0.0)
        self.assertEqual(initial.relative, (state.radius_m, 0.0, 0.0))
        quarter = state_at_time(state, state.period_s / 4.0)
        self.assertLess(abs(quarter.relative[0]), state.radius_m * 1.0e-14)
        self.assertRelative(quarter.relative[1], state.radius_m)
        self.assertRelative(quarter.relative_velocity[0], -state.speed_m_s)

    def test_periodicity_phase_and_time_reversal(self) -> None:
        state = BohrState(2)
        first = state_at_time(state, state.period_s * 0.125)
        after_periods = state_at_time(state, state.period_s * 4.125)
        phase_shifted = state_at_time(state, 0.0, math.pi / 4.0)
        backwards = state_at_time(state, -state.period_s * 0.125)
        self.assertRelative(first.relative[0], after_periods.relative[0])
        self.assertRelative(first.relative[1], after_periods.relative[1])
        self.assertRelative(first.relative[0], phase_shifted.relative[0])
        self.assertRelative(first.relative[1], phase_shifted.relative[1])
        self.assertRelative(backwards.relative[0], first.relative[0])
        self.assertRelative(backwards.relative[1], -first.relative[1])

    def test_positions_velocities_and_com_for_both_particles(self) -> None:
        state = BohrState(5)
        for fraction in (0.0, 0.17, 0.39, 0.71, 1.13):
            sample = state_at_time(state, fraction * state.period_s)
            self.assertRelative(magnitude(sample.relative), state.radius_m)
            self.assertRelative(magnitude(sample.electron), state.electron_radius_m)
            self.assertRelative(magnitude(sample.proton), state.proton_radius_m)
            self.assertRelative(magnitude(sample.relative_velocity), state.speed_m_s)
            separation_x = sample.electron[0] - sample.proton[0]
            separation_y = sample.electron[1] - sample.proton[1]
            self.assertAlmostEqual(
                separation_x / state.radius_m, sample.relative[0] / state.radius_m
            )
            self.assertAlmostEqual(
                separation_y / state.radius_m, sample.relative[1] / state.radius_m
            )
            weighted_x = ELECTRON_MASS * sample.electron[0] + PROTON_MASS * sample.proton[0]
            weighted_y = ELECTRON_MASS * sample.electron[1] + PROTON_MASS * sample.proton[1]
            com_scale = ELECTRON_MASS * state.radius_m
            self.assertLess(abs(weighted_x), com_scale * 1.0e-14)
            self.assertLess(abs(weighted_y), com_scale * 1.0e-14)
            total_px = (
                ELECTRON_MASS * sample.electron_velocity[0]
                + PROTON_MASS * sample.proton_velocity[0]
            )
            total_py = (
                ELECTRON_MASS * sample.electron_velocity[1]
                + PROTON_MASS * sample.proton_velocity[1]
            )
            momentum_scale = ELECTRON_MASS * state.speed_m_s
            self.assertLess(abs(total_px), momentum_scale * 1.0e-14)
            self.assertLess(abs(total_py), momentum_scale * 1.0e-14)

    def test_kinetic_identity_for_two_moving_particles(self) -> None:
        state = BohrState(6)
        sample = state_at_time(state, state.period_s * 0.23)
        electron_kinetic = 0.5 * ELECTRON_MASS * magnitude(sample.electron_velocity) ** 2
        proton_kinetic = 0.5 * PROTON_MASS * magnitude(sample.proton_velocity) ** 2
        self.assertRelative(electron_kinetic + proton_kinetic, state.kinetic_j)

    def test_velocity_is_derivative_of_position(self) -> None:
        state = BohrState(4)
        time = 0.137 * state.period_s
        step = state.period_s * 1.0e-6
        previous = state_at_time(state, time - step)
        following = state_at_time(state, time + step)
        current = state_at_time(state, time)
        velocity_x = (following.relative[0] - previous.relative[0]) / (2.0 * step)
        velocity_y = (following.relative[1] - previous.relative[1]) / (2.0 * step)
        self.assertRelative(velocity_x, current.relative_velocity[0], 1.0e-9)
        self.assertRelative(velocity_y, current.relative_velocity[1], 1.0e-9)

    def test_acceleration_obeys_newtons_law(self) -> None:
        state = BohrState(3)
        time = state.period_s * 0.19
        step = state.period_s * 1.0e-6
        previous = state_at_time(state, time - step)
        following = state_at_time(state, time + step)
        current = state_at_time(state, time)
        acceleration_x = (following.electron_velocity[0] - previous.electron_velocity[0]) / (
            2.0 * step
        )
        acceleration_y = (following.electron_velocity[1] - previous.electron_velocity[1]) / (
            2.0 * step
        )
        force_factor = -KAPPA / state.radius_m**3
        force_x = force_factor * current.relative[0]
        force_y = force_factor * current.relative[1]
        self.assertRelative(ELECTRON_MASS * acceleration_x, force_x, 1.0e-9)
        self.assertRelative(ELECTRON_MASS * acceleration_y, force_y, 1.0e-9)

    def test_fixed_proton_does_not_move(self) -> None:
        state = BohrState(1, False)
        sample = state_at_time(state, state.period_s * 0.3)
        self.assertEqual(sample.proton, (0.0, 0.0, 0.0))
        self.assertEqual(sample.proton_velocity, (0.0, 0.0, 0.0))
        self.assertEqual(sample.electron, sample.relative)
        self.assertRelative(magnitude(sample.electron_velocity), state.speed_m_s)

    def test_input_validation_and_large_finite_times(self) -> None:
        state = BohrState()
        for bad in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                state_at_time(state, bad)
            with self.assertRaises(ValueError):
                state_at_time(state, 0.0, bad)
        for bad in (True, "0", None):
            with self.assertRaises(TypeError):
                state_at_time(state, bad)
        with self.assertRaises(TypeError):
            state_at_time(None, 0.0)
        sample = state_at_time(state, 1.0e300, 1.0e300)
        self.assertRelative(magnitude(sample.relative), state.radius_m)


class TransitionTests(RelativeAssertions):
    def test_balmer_alpha_vacuum_wavelength_and_energy(self) -> None:
        result = transition(3, 2)
        self.assertEqual((result.initial_n, result.final_n), (3, 2))
        self.assertGreater(result.energy_j, 0.0)
        self.assertRelative(result.wavelength_nm, 656.47, 2.0e-5)
        self.assertRelative(result.energy_ev, 1.88865, 1.0e-5)

    def test_lyman_alpha_and_adjacent_high_n_transition(self) -> None:
        self.assertRelative(transition(2, 1).wavelength_nm, 121.568, 1.0e-5)
        high = transition(12, 11)
        self.assertGreater(high.wavelength_nm, transition(3, 2).wavelength_nm)
        self.assertGreater(high.energy_j, 0.0)

    def test_energy_conservation_frequency_and_units(self) -> None:
        result = transition(8, 2)
        self.assertRelative(result.energy_j, BohrState(8).energy_j - BohrState(2).energy_j)
        self.assertRelative(H * result.frequency_hz, result.energy_j)
        self.assertRelative(C / result.frequency_hz * 1.0e9, result.wavelength_nm)
        self.assertRelative(result.energy_ev * E_CHARGE, result.energy_j)

    def test_mass_correction_matches_independent_rydberg_scaling(self) -> None:
        finite = transition(3, 2, True)
        fixed = transition(3, 2, False)
        scale = 1.0 + ELECTRON_MASS / PROTON_MASS
        self.assertRelative(finite.wavelength_nm / fixed.wavelength_nm, scale)
        self.assertRelative(fixed.frequency_hz / finite.frequency_hz, scale)

    def test_invalid_emissions(self) -> None:
        for pair in ((1, 1), (1, 2), (3, 4), (13, 1), (2, 0)):
            with self.assertRaises(ValueError):
                transition(pair[0], pair[1])
        with self.assertRaises(TypeError):
            transition(True, 1)


class ClassicalPotentialTests(RelativeAssertions):
    def test_circle_radius_is_continuous_before_quantization(self) -> None:
        scale = 1.35
        radius = classical_radius(scale * HBAR, False)
        self.assertRelative(radius, scale * scale * A0)
        self.assertRelative(classical_radius(3.0 * HBAR), BohrState(3).radius_m)

    def test_effective_potential_has_minimum_at_calculated_circle(self) -> None:
        state = BohrState(4)
        radius = state.radius_m
        momentum = state.angular_momentum
        step = radius * 1.0e-4
        center = effective_potential(radius, momentum)
        left = effective_potential(radius - step, momentum)
        right = effective_potential(radius + step, momentum)
        self.assertRelative(center, state.energy_j)
        self.assertGreater(left, center)
        self.assertGreater(right, center)
        derivative = (right - left) / (2.0 * step)
        derivative_scale = KAPPA / radius**2
        self.assertLess(abs(derivative), derivative_scale * 3.0e-8)
        curvature = (right - 2.0 * center + left) / step**2
        self.assertRelative(curvature, KAPPA / radius**3, 2.0e-7)

    def test_zero_angular_momentum_has_only_coulomb_potential(self) -> None:
        self.assertRelative(effective_potential(A0, 0.0), -KAPPA / A0)

    def test_invalid_inputs(self) -> None:
        for bad in (0.0, -A0, math.nan, math.inf):
            with self.assertRaises(ValueError):
                effective_potential(bad, HBAR)
        for bad in (-HBAR, math.nan, math.inf):
            with self.assertRaises(ValueError):
                effective_potential(A0, bad)
        for bad in (0.0, -HBAR, math.nan, math.inf):
            with self.assertRaises(ValueError):
                classical_radius(bad)
        with self.assertRaises(TypeError):
            effective_potential(A0, HBAR, 1)
        with self.assertRaises(TypeError):
            classical_radius(True)

    def test_unrepresentable_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            effective_potential(1.0e-300, HBAR)
        with self.assertRaises(ValueError):
            classical_radius(1.0e300)
        with self.assertRaises(ValueError):
            classical_radius(1.0e-300)


if __name__ == "__main__":
    unittest.main()
