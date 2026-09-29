"""Reuse unchanged CP4 analytical install checks for the independently rebuilt archives."""

import importlib.util
import shutil
import sys

from collect import CLONE
from run_check import EVIDENCE, WORK

if __name__ == "__main__":
    source = CLONE / "experiments/M6_CP4_FINAL_20260928"
    for name in ("analysis-requirements.txt", "installed_api_check.py"):
        target = EVIDENCE / name
        assert not target.exists()
        shutil.copyfile(source / name, target)
        assert target.read_bytes() == (source / name).read_bytes()
    spec = importlib.util.spec_from_file_location("cp4_installs", source / "verify_installs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = CLONE
    module.EVIDENCE = EVIDENCE
    sys.argv = [str(source / "verify_installs.py"), str(WORK / "package-installs-01"),
                str(WORK / "build-01"), "clone-build-01"]
    raise SystemExit(module.main())
