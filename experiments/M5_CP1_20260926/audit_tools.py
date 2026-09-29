"""Reproduce CP1 independent derivative/convergence and deliberate mutation gates.

Run only when no other process uses source.py; original bytes restored in finally.
Mutation subprocesses have separate bytecode roots to avoid same-second cache reuse.
"""

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from kineimu_shoulder.validation import oracle, source

ROOT = Path(__file__).resolve().parents[2]


def numerical():
    maximum = 0.0
    errors = []
    for hz in (100, 200):
        data = source.generate("T-MIX", sample_hz=hz)
        row = data.nodes["B"]
        rotation = Rotation.from_quat(row.q_ws[0], scalar_first=True)
        integration_error = 0.0
        for i in range(1, len(row.sequence)):
            rotation = rotation * Rotation.from_rotvec(
                row.rate_rads[i] * (row.true_time_us[i] - row.true_time_us[i - 1]) / 1e6
            )
            integration_error = max(
                integration_error, (rotation.inv() * Rotation.from_quat(row.q_ws[i], scalar_first=True)).magnitude()
            )
        errors.append(integration_error)
        for node in ("A", "B"):
            for i in range(537 * hz // 100, len(row.sequence) - 1, 31):
                ref = oracle.sensor_reference("T-MIX", node, row.true_time_us[i] / 1e6)
                observed = data.nodes[node].rate_rads[i]
                maximum = max(maximum, float(np.max(np.abs(observed - ref[1]))))
    assert maximum <= 1e-6
    assert errors[0] <= np.pi / 450
    assert errors[1] / errors[0] <= 0.75
    return {
        "derivative_max_component_error_rads": maximum,
        "mixed_integration_max_error_rad_100_200": errors,
        "halved_dt_error_ratio": errors[1] / errors[0],
        "derivative_step_s": 1e-5,
        "disposition": "PASS",
    }


def mutations():
    path = ROOT / "kineimu_shoulder/validation/source.py"
    original = path.read_bytes()
    text = original.decode("utf-8")
    recipes = [
        ("gyro-sign", "gyro = (ns.inv() * nk).apply(body)", "gyro = -(ns.inv() * nk).apply(body)", "o1_o4"),
        ("composition-order", "else thorax * relative", "else relative * thorax", "o5_t1"),
        ("claimed-dt", "scale * claimed + offset", "scale * nominal + offset", "p3_p4_p7"),
        ("renumber-loss", "sequence[keep],", "np.arange(int(keep.sum()), dtype=np.int64),", "p5_p6"),
    ]
    results = []
    try:
        for name, before, after, selection in recipes:
            assert text.count(before) == 1
            path.write_bytes(text.replace(before, after).encode("utf-8"))
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    f"pycache_prefix={ROOT / '.tmp-m5-cp1-mutation-cache' / name}",
                    "-m",
                    "pytest",
                    "tests/unit/test_m5_source.py",
                    "-q",
                    "-k",
                    selection,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1 and "FAILED" in result.stdout and "ERROR" not in result.stdout, (
                result.stdout + result.stderr
            )
            results.append(
                {
                    "mutation": name,
                    "test_selection": selection,
                    "exit_code": result.returncode,
                    "test_summary": result.stdout.strip().splitlines()[-1],
                    "disposition": "CAUGHT",
                }
            )
            path.write_bytes(original)
    finally:
        path.write_bytes(original)
    assert path.read_bytes() == original
    return {"source_sha256_before_after": sha256(original).hexdigest(), "restored": True, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    result = {
        "source_type": "synthetic",
        "scope": "CP1 tools; no AHRS/physical/clinical accuracy",
        "numerical": numerical(),
    }
    if args.mutations:
        result["mutations"] = mutations()
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
