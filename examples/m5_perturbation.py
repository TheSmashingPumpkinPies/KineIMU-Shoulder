"""Execute frozen M5 CP3 matrix, retaining every result."""

import argparse
from pathlib import Path

from kineimu_shoulder.validation.perturbation import export

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--development", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    try:
        passed = export(a.output, formal=not a.development, workers=a.workers)
    except (ValueError, FileExistsError) as exc:
        p.exit(2, f"blocked: {exc}\n")
    raise SystemExit(0 if passed else 1)
