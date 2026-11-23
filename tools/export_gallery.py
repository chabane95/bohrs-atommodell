"""Export the deliberately selected 4K stills used alongside the derivation."""

from pathlib import Path

from bohr_atom.export import export_still
from bohr_atom.renderer import RenderSettings

# Explicit shot list: scene, quantum number, seconds in the 36-second camera move.
SHOTS = (
    ("orbit", 1, 6),
    ("orbit", 1, 18),
    ("orbit", 1, 32),
    ("vectors", 1, 6),
    ("vectors", 1, 18),
    ("vectors", 1, 32),
    ("quantization", 3, 6),
    ("quantization", 3, 18),
    ("quantization", 3, 32),
    ("comparison", 1, 6),
    ("comparison", 1, 18),
    ("comparison", 1, 32),
    ("energy", 1, 6),
    ("energy", 1, 18),
    ("energy", 1, 32),
    ("spectrum", 3, 6),
    ("spectrum", 3, 14),
    ("spectrum", 3, 32),
    ("orbital", 1, 6),
    ("orbital", 1, 18),
    ("orbital", 1, 32),
    ("orbit", 2, 18),
    ("orbit", 3, 18),
    ("orbit", 4, 18),
    ("orbit", 5, 18),
    ("orbit", 6, 18),
    ("spectrum", 4, 32),
    ("spectrum", 5, 32),
    ("spectrum", 6, 32),
    ("energy", 2, 18),
    ("energy", 3, 18),
)


def main() -> None:
    output = Path("outputs/Standbilder")
    settings = RenderSettings(width=3840, height=2160)
    for index, (scene, n, seconds) in enumerate(SHOTS, 1):
        path = output / f"{index:02d}_{scene}_n{n}_{seconds:02d}s.png"
        export_still(scene, settings, path, n=n, seconds=seconds, supersample=1)
        print(path, flush=True)


if __name__ == "__main__":
    main()
