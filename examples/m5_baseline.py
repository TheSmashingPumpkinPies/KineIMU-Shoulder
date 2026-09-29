"""Run the frozen CP2 clean baseline; exit 1 retains failed acceptance evidence."""

import argparse
from pathlib import Path

from kineimu_shoulder.validation.baseline import export

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development", action="store_true",
                        help="nonformal diagnostic run, permits dirty tracked code")
    args = parser.parse_args()
    try:
        passed = export(args.output, formal=not args.development)
    except (ValueError, FileExistsError) as exc:
        parser.exit(2, f"blocked: {exc}\n")
    raise SystemExit(0 if passed else 1)
