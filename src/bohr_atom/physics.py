"""Explicit Bohr hydrogen model in SI units, using only the standard library.

The quantization rule L = n*hbar and nonradiating allowed orbits are postulates.
This module computes their consequences, not quantum electron trajectories.
With finite nuclear mass, radii and speeds describe the relative coordinate.
"""

import math
from dataclasses import dataclass

# CODATA 2022 central values. h, c and the elementary charge are exact in SI.
H: float = 6.62607015e-34
HBAR: float = H / math.tau
C: float = 299_792_458.0
E_CHARGE: float = 1.602176634e-19
ELECTRON_MASS: float = 9.1093837139e-31
PROTON_MASS: float = 1.67262192595e-27
VACUUM_PERMITTIVITY: float = 8.8541878188e-12
KAPPA: float = E_CHARGE * E_CHARGE / (4.0 * math.pi * VACUUM_PERMITTIVITY)
A0: float = HBAR * HBAR / (ELECTRON_MASS * KAPPA)
MAX_N: int = 12

Vector3 = tuple[float, float, float]


def _finite_float(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, not a boolean.")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite.") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _mass(finite_mass: bool) -> float:
    if type(finite_mass) is not bool:
        raise TypeError("finite_mass must be a boolean.")
    if finite_mass:
        total_mass = ELECTRON_MASS + PROTON_MASS
        return ELECTRON_MASS * PROTON_MASS / total_mass
    return ELECTRON_MASS


@dataclass(frozen=True)
class BohrState:
    """One allowed circular hydrogen orbit. finite_mass=False fixes the proton."""

    n: int = 1
    finite_mass: bool = True

    def __post_init__(self) -> None:
        if type(self.n) is not int:
            raise TypeError("n must be an integer, not a boolean or float.")
        if self.n < 1 or self.n > MAX_N:
            raise ValueError("n must be between 1 and 12.")
        _mass(self.finite_mass)

    @property
    def reduced_mass_kg(self) -> float:
        return _mass(self.finite_mass)

    @property
    def length_scale_m(self) -> float:
        return HBAR * HBAR / (self.reduced_mass_kg * KAPPA)

    @property
    def radius_m(self) -> float:
        """Constant electron-proton separation, not electron COM radius."""
        return self.length_scale_m * self.n * self.n

    @property
    def electron_radius_m(self) -> float:
        if not self.finite_mass:
            return self.radius_m
        total_mass = ELECTRON_MASS + PROTON_MASS
        return PROTON_MASS / total_mass * self.radius_m

    @property
    def proton_radius_m(self) -> float:
        if not self.finite_mass:
            return 0.0
        total_mass = ELECTRON_MASS + PROTON_MASS
        return ELECTRON_MASS / total_mass * self.radius_m

    @property
    def angular_momentum(self) -> float:
        """Relative orbital angular-momentum magnitude in kg m^2 / s."""
        return self.n * HBAR

    @property
    def speed_m_s(self) -> float:
        """Relative speed. The individual COM speeds differ by mass fractions."""
        return KAPPA / self.angular_momentum

    @property
    def omega_rad_s(self) -> float:
        return self.speed_m_s / self.radius_m

    @property
    def period_s(self) -> float:
        return math.tau / self.omega_rad_s

    @property
    def kinetic_j(self) -> float:
        relative_speed = self.speed_m_s
        return 0.5 * self.reduced_mass_kg * relative_speed * relative_speed

    @property
    def potential_j(self) -> float:
        return -KAPPA / self.radius_m

    @property
    def energy_j(self) -> float:
        momentum = self.angular_momentum
        numerator = self.reduced_mass_kg * KAPPA * KAPPA
        return -numerator / (2.0 * momentum * momentum)

    @property
    def energy_ev(self) -> float:
        return self.energy_j / E_CHARGE


@dataclass(frozen=True)
class OrbitSnapshot:
    """Positions in metres and velocities in m/s in the COM xy plane."""

    relative: Vector3
    electron: Vector3
    proton: Vector3
    relative_velocity: Vector3
    electron_velocity: Vector3
    proton_velocity: Vector3


def state_at_time(state: BohrState, t_s: float, phase: float = 0.0) -> OrbitSnapshot:
    """Exact circular motion; positive time rotates +x toward +y.

    The initial phase is in radians. The COM is at rest at the origin.
    Period reduction avoids overflowing omega*t for a large finite input time;
    resolving an absolute time still depends on the precision of its float.
    """
    if not isinstance(state, BohrState):
        raise TypeError("state must be a BohrState.")
    time_seconds = _finite_float(t_s, "t_s")
    phase_radians = _finite_float(phase, "phase")
    reduced_time = math.remainder(time_seconds, state.period_s)
    reduced_phase = math.remainder(phase_radians, math.tau)
    angle = math.tau * (reduced_time / state.period_s) + reduced_phase
    cosine = math.cos(angle)
    sine = math.sin(angle)

    radius = state.radius_m
    speed = state.speed_m_s
    relative = (radius * cosine, radius * sine, 0.0)
    relative_velocity = (-speed * sine, speed * cosine, 0.0)

    electron_radius = state.electron_radius_m
    proton_radius = state.proton_radius_m
    electron_speed = electron_radius * state.omega_rad_s
    proton_speed = proton_radius * state.omega_rad_s
    electron = (electron_radius * cosine, electron_radius * sine, 0.0)
    proton = (-proton_radius * cosine, -proton_radius * sine, 0.0)
    electron_velocity = (-electron_speed * sine, electron_speed * cosine, 0.0)
    proton_velocity = (proton_speed * sine, -proton_speed * cosine, 0.0)
    return OrbitSnapshot(
        relative=relative,
        electron=electron,
        proton=proton,
        relative_velocity=relative_velocity,
        electron_velocity=electron_velocity,
        proton_velocity=proton_velocity,
    )


@dataclass(frozen=True)
class Transition:
    """Energy bookkeeping for one selected emission, not transition dynamics."""

    initial_n: int
    final_n: int
    energy_j: float
    energy_ev: float
    frequency_hz: float
    wavelength_nm: float


def transition(ni: int, nf: int, finite_mass: bool = True) -> Transition:
    """Compute positive photon energy and vacuum wavelength for ni > nf.

    No duration, rate, intensity, selection rule or electron path is implied.
    Atomic recoil due to the emitted photon is beyond this Bohr approximation.
    """
    initial = BohrState(ni, finite_mass)
    final = BohrState(nf, finite_mass)
    if ni <= nf:
        raise ValueError("Emission requires initial n greater than final n.")
    photon_energy = initial.energy_j - final.energy_j
    photon_frequency = photon_energy / H
    wavelength_m = C / photon_frequency
    return Transition(
        initial_n=ni,
        final_n=nf,
        energy_j=photon_energy,
        energy_ev=photon_energy / E_CHARGE,
        frequency_hz=photon_frequency,
        wavelength_nm=wavelength_m * 1.0e9,
    )


def effective_potential(
    radius_m: float, angular_momentum: float, finite_mass: bool = True
) -> float:
    """U_eff = L^2/(2*mu*r^2) - kappa/r, in joules; L is a magnitude.

    The first term is the angular part of kinetic energy. This is a classical
    radial energy landscape at fixed L, not a quantum radial wave equation.
    """
    radius = _finite_float(radius_m, "radius_m")
    momentum = _finite_float(angular_momentum, "angular_momentum")
    reduced_mass = _mass(finite_mass)
    if radius <= 0.0:
        raise ValueError("radius_m must be positive.")
    if momentum < 0.0:
        raise ValueError("angular_momentum must be nonnegative.")
    tangential_momentum = momentum / radius
    angular_energy = tangential_momentum * tangential_momentum / (2.0 * reduced_mass)
    coulomb_energy = -KAPPA / radius
    energy = angular_energy + coulomb_energy
    if not math.isfinite(energy):
        raise ValueError("Effective potential exceeds the floating-point range.")
    return energy


def classical_radius(angular_momentum: float, finite_mass: bool = True) -> float:
    """Radius of a classical circular hydrogen orbit for any positive L."""
    momentum = _finite_float(angular_momentum, "angular_momentum")
    reduced_mass = _mass(finite_mass)
    if momentum <= 0.0:
        raise ValueError("angular_momentum must be positive for a circular orbit.")
    radius = momentum * momentum / (reduced_mass * KAPPA)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("Classical radius exceeds the positive floating-point range.")
    return radius
