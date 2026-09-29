"""Complete predeclared M5 finite case expansion; no pipeline results or tuning.

Path/mechanism/sign/map controls are encoded in condition IDs to preserve unique
trajectory/condition/target/seed IDs. Boundary/evidence cases are runner recipes,
not claims that the sensor source executes evidence gates.
"""

from dataclasses import asdict
from itertools import product
from math import pi
from typing import Any

from kineimu_shoulder.validation.motions import MOTIONS
from kineimu_shoulder.validation.source import Perturbation

SEEDS = (1103, 2207, 3301, 4409, 5519)
TARGETS = ("A", "B", "SAME", "DIFF")
BASELINES = ("F90", "AL90", "AR90")


def cases() -> list[dict[str, Any]]:
    """Expand every finite CP0 factor, interaction, malformed and evidence control."""
    rows: list[dict[str, Any]] = []

    def add(
        trajectory: str,
        condition: str,
        target: str = "SAME",
        seed: int = 0,
        path: str = "S",
        kind: str = "W",
        recipe: str = "sensor-source",
        **parameters: Any,
    ) -> None:
        rows.append(
            {
                "id": f"{trajectory}/{condition}/{target}/{seed}",
                "trajectory": trajectory,
                "condition": condition,
                "target": target,
                "seed": seed,
                "path": path,
                "class": kind,
                "implementation": recipe,
                "parameters": parameters,
                "control_id": f"{trajectory}/CLEAN-{path}/SAME/0",
            }
        )

    for trajectory in MOTIONS:
        for path in ("E", "S"):
            add(
                trajectory,
                f"CLEAN-{path}",
                path=path,
                kind="C",
                recipe="exact-source" if path == "E" else "sensor-source",
            )
    for trajectory in (*BASELINES, "T-MIX"):
        add(trajectory, "CLEAN-Q", path="Q", kind="C")
    for family, values, field in (
        ("N-A", (0.005, 0.02, 0.20), "accel_sigma"),
        ("N-G", (0.001, 0.005, 0.05), "gyro_sigma"),
        ("J-S", (100, 1000, 6000), "sample_jitter_us"),
        ("J-T", (100, 1000, 6000), "timestamp_jitter_us"),
    ):
        for (level, value), trajectory, target, seed in product(
            zip(("L", "H", "X"), values, strict=True), BASELINES, TARGETS[:3], SEEDS
        ):
            kwargs: dict[str, Any] = {field: value}
            add(trajectory, f"{family}-{level}", target, seed, kind="stress" if level == "X" else "W", **kwargs)
    for family, values, field in (("B-C", (0.002, 0.02, 1), "bias_rads"), ("B-R", (0.004, 0.04, 2), "ramp_rads")):
        for (level, value), trajectory, target in product(
            zip(("L", "H", "X"), values, strict=True), (*BASELINES, "F90L"), TARGETS
        ):
            kind = "stress" if level == "X" or (trajectory == "F90L" and level == "H") else "W"
            bias_parameters: dict[str, Any] = {field: value * pi / 180}
            add(trajectory, f"{family}-{level}", target, kind=kind, **bias_parameters)
    for family, path, prefix in (("L-S", "S", "sample"), ("L-P", "Q", "packet")):
        for level, trajectory, target in product(("ONE", "PER", "BURST"), BASELINES, TARGETS[:3]):
            add(
                trajectory,
                f"{family}-{level}",
                target,
                path=path,
                kind="rejection" if level == "BURST" else "W",
                loss=f"{prefix}-{level.lower()}",
            )
    for trajectory, (level, ppm), mapping in product(
        (*BASELINES, "F90L"),
        (
            ("0", 0),
            ("L-plus", 100),
            ("L-minus", -100),
            ("H-plus", 500),
            ("H-minus", -500),
            ("X-plus", 5000),
            ("X-minus", -5000),
        ),
        ("exact", "wrong"),
    ):
        add(
            trajectory,
            f"D-C-{level}-{mapping}",
            "B",
            kind="stress" if level.startswith("X") or mapping == "wrong" else "W",
            clock_ppm=ppm,
            clock_enabled=True,
            map_control=mapping,
        )
    for trajectory, (level, rate), target, mechanism in product(
        (*BASELINES, "F90L"), (("L", 0.002), ("H", 0.02), ("X", 0.2)), TARGETS, ("sensor", "world")
    ):
        path = "S" if mechanism == "sensor" else "E"
        kind = "stress" if level == "X" or (trajectory == "F90L" and level == "H") else "W"
        add(
            trajectory,
            f"D-H-{level}-{mechanism}",
            target,
            path=path,
            kind=kind,
            heading_rate_rads=rate * pi / 180,
            heading_path=mechanism,
        )
    for trajectory, seed in product(BASELINES, SEEDS):
        add(trajectory, "I-NB", "DIFF", seed, accel_sigma=0.02, gyro_sigma=0.005, bias_rads=0.02 * pi / 180)
        add(trajectory, "I-JL", "SAME", seed, sample_jitter_us=1000, loss="sample-per")
    for duration, trajectory in ((30, "F90-30"), (300, "F90L")):
        add(
            trajectory,
            f"I-HD-{duration}",
            "DIFF",
            kind="W" if duration == 30 else "stress",
            heading_rate_rads=0.02 * pi / 180,
            evaluation_duration_s=duration,
        )
    for trajectory in BASELINES:
        add(trajectory, "C-APPLY", kind="C", calibration=True)
        for level, seed in product(("L", "H"), SEEDS):
            add(
                trajectory,
                f"C-FIT-{level}",
                "SAME",
                seed,
                accel_sigma=0.02,
                gyro_sigma=0.005,
                bias_rads=(0.002 if level == "L" else 0.02) * pi / 180,
                fit_gyro=True,
            )
    for gap, path in product((49999, 50000, 50001), ("E", "S")):
        add(
            "F90",
            f"GAP-{gap}-{path}",
            path=path,
            kind="rejection" if gap > 50000 and path == "S" else "boundary",
            recipe="irregular-grid",
            gap_us=gap,
        )
    for mutation in (
        "duplicate-time",
        "reverse-time",
        "epoch-reset",
        "empty",
        "one-row",
        "nan-force",
        "inf-force",
        "nan-rate",
        "inf-rate",
        "zero-force",
        "accel-range",
        "gyro-range",
        "accel-clipped",
        "gyro-clipped",
        "crc",
        "hash",
        "node",
    ):
        add(
            "F90",
            f"INPUT-{mutation}",
            kind="boundary" if mutation in ("epoch-reset", "one-row") else "rejection",
            recipe="input-mutation",
            mutation=mutation,
        )
    mutations = ["map-A", "map-B", "heading", "align-A", "align-B", "trace"]
    for record in ("map-A", "map-B", "heading", "align-A", "align-B", "trace"):
        for field in ("node", "hash", "epoch", "world", "side"):
            mutations.append(f"{record}-{field}")
    for record in ("map-A", "map-B", "align-A", "align-B"):
        mutations.extend((f"{record}-expired", f"{record}-assumed"))
    mutations.extend(
        (
            "heading-assumed",
            "align-A-remount",
            "align-B-remount",
            "uncertainty-1999",
            "uncertainty-2000",
            "uncertainty-2001",
            "drift-below",
            "drift-equal",
            "drift-above",
            "drift-uncovered",
            "singularity-T8",
            "branch-T9",
        )
    )
    mutations.extend(f"comparison-{v}" for v in ("remount", "backend", "threshold", "source-type", "evidence"))
    for mutation, path in product(mutations, ("E", "S")):
        add("F90", f"EV-{mutation}-{path}", path=path, kind="evidence", recipe="evidence-mutation", mutation=mutation)
    for fixture in (
        "C0",
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
        "C9",
        "C10",
        "C11",
        "C12",
        "C13",
        "C14",
        "C15",
        "C16",
        "C17",
        "C18",
        "C19",
        "C20",
        "C21",
        *[f"P{i}" for i in range(11)],
        *[f"T{i}" for i in range(16)],
        *[f"U{i}" for i in range(11)],
    ):
        add("F90", f"M4-{fixture}", path="E", kind="boundary", recipe="existing-M4-fixture", fixture=fixture)
    order = {target: index for index, target in enumerate(TARGETS)}
    rows.sort(key=lambda r: (r["trajectory"], r["condition"], order.get(r["target"], 4), r["target"], r["seed"]))
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("duplicate finite case ID")
    return rows


def perturbation_for(row: dict[str, Any]) -> Perturbation:
    """Resolve source parameters; evidence/grid recipes remain explicit runner work."""
    if row["implementation"] != "sensor-source":
        raise ValueError("case requires an explicit downstream/grid/evidence runner recipe")
    parameters = row["parameters"]
    fields = asdict(Perturbation())
    values = {k: v for k, v in parameters.items() if k in fields}
    return Perturbation(seed=row["seed"], target=parameters.get("injection_target", row["target"]), **values)
