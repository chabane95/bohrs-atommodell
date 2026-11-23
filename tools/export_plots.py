"""Export Bohr figures without opening a GPU window."""

import argparse
from pathlib import Path

from bohr_atom.presentation import export_plots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/Plots"))
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--fixed-proton", action="store_true")
    args = parser.parse_args()
    paths = export_plots(args.output, not args.fixed_proton, args.width, args.height)
    for path in paths:
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
