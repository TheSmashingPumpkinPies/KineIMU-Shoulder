"""CP1 finite expansion gates: omissions, seeds, target signs, paths and classes."""

import importlib.util
from collections import Counter


def test_complete_manifest_exists():
    assert importlib.util.find_spec("kineimu_shoulder.validation.manifest") is not None


def test_finite_expansion_seed_and_matching_controls():
    from kineimu_shoulder.validation.manifest import cases

    rows = cases()
    assert len({r["id"] for r in rows}) == len(rows)
    noise = [r for r in rows if r["condition"].startswith(("N-A-", "N-G-"))]
    assert len(noise) == 270  # 6 conditions * 3 trajectories * 3 targets * 5 seeds
    assert Counter(r["seed"] for r in noise) == {1103: 54, 2207: 54, 3301: 54, 4409: 54, 5519: 54}
    for row in rows:
        assert row["control_id"] in {r["id"] for r in rows}
    assert (
        len([r for r in rows if r["condition"].startswith("D-C-")]) == 56
    )  # 4 trajectories * 7 signed levels * 2 maps
    assert len([r for r in rows if r["condition"].startswith("D-H-")]) == 96  # 4*3*4 targets*2 mechanisms
    assert len([r for r in rows if r["condition"].startswith("L-P-")]) == 27
    assert len([r for r in rows if r["condition"].startswith("C-FIT-")]) == 30
    assert {r["parameters"]["gap_us"] for r in rows if r["condition"].startswith("GAP-")} == {49999, 50000, 50001}
    assert {
        r["path"] for r in rows if r["condition"].startswith("EV-map-A-") and r["parameters"]["mutation"] == "map-A"
    } == {"E", "S"}
    long_high = [r for r in rows if r["trajectory"] == "F90L" and r["condition"] == "B-C-H"]
    assert all(r["class"] == "stress" for r in long_high)


def test_every_sensor_matrix_condition_resolves_before_launch():
    from kineimu_shoulder.validation.manifest import cases, perturbation_for
    from kineimu_shoulder.validation.source import generate

    seen = set()
    for row in cases():
        if row["implementation"] != "sensor-source":
            continue
        p = perturbation_for(row)
        key = (row["condition"], row["target"], row["trajectory"] == "F90L")
        if key in seen:
            continue
        seen.add(key)
        data = generate(str(row["trajectory"]), p)
        assert data.nodes["A"].force_mps2.shape[1] == 3
