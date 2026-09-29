"""Record actual interpreter identity before unchanged Demo imports (inside timing)."""

import argparse
import json
import os
import runpy
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
identity = dict(pid=os.getpid(), ppid=os.getppid(), executable=sys.executable,
                threads={k: os.environ.get(k) for k in
                         ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
                external_m1_root=os.environ.get("KINEIMU_M1_RAW_ROOT"), process_argv=list(sys.orig_argv))
# Keep original OS argv within CP2's --output-only variation whitelist.
with (args.output.parent / "worker.json").open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(identity, sort_keys=True, indent=2) + "\n")
demo = Path(__file__).resolve().parents[2] / "examples/m6_demo.py"
sys.argv = [str(demo), "--output", str(args.output)]
runpy.run_path(str(demo), run_name="__main__")
