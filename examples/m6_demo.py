"""One command from immutable dual-node sensor replay to readable shoulder metrics."""

import sys
from pathlib import Path

# Locate the repository from the script, independent of caller cwd or PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kineimu_shoulder.validation.demo import main

if __name__ == "__main__":
    main()
