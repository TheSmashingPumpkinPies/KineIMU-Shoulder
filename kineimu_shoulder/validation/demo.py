"""M6 presentation and run bookkeeping around the unchanged stored-Q exporter.

Repository-clone convenience entry; no sensor generation or scientific algorithm.
The M5 report retains its original checkpoint meaning. Run metadata is M6-only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "datasets/samples/m6_synthetic"
TRAJECTORIES = ("F90", "AL90", "AR90", "T-MIX")
CONTRACT = "m6-demo-contract/1.0"
LIMITATIONS = [
    "Synthetic stored sensor observations; anatomical_eligible=false; INTERNAL ONLY / redistribution pending.",
    "Known calibration, initialization, alignment, heading and clock are Assumed construction conditions.",
    "Static gravity does not determine full heading; independent AHRS worlds cannot be composed automatically.",
    "Humerothoracic metrics and thorax excursion proxy; no clinical, glenohumeral or scapular validation.",
    "Four different exercise/side trajectories are not longitudinal rehabilitation outcomes.",
    "Repository clone required; wheel-only demo, Linux execution and performance acceptance are not established.",
]


def _read(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    if path.suffix == ".gz":
        content = gzip.decompress(content)
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError(f"missing object in {path.name}")
    return cast(dict[str, Any], value)


def _write(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _protect(output: Path, input_root: Path) -> None:
    # Resolve before checking: includes Windows junction and symlink targets.
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    protected = [input_root, ROOT]
    if any(part.lower() == "raw" for part in output.parts):
        raise ValueError("output has a protected raw path component")
    if output.is_relative_to(ROOT):
        relative = output.relative_to(ROOT)
        if len(relative.parts) != 1 or not relative.name.startswith("demo-output-"):
            raise ValueError("repository output must be a new top-level demo-output-* directory")
        protected = [input_root, *(p.resolve() for p in ROOT.iterdir() if p.is_dir())]
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in protected):
        raise ValueError("output overlaps a protected repository or input tree")
    # Keep the established M5 guards, including source/evidence/raw anchors.
    from kineimu_shoulder.io.m1_packet import NodeId
    from kineimu_shoulder.validation.replay import ReplayInput
    from kineimu_shoulder.validation.replay import _protect as protect_replay

    anchors = tuple(ReplayInput(f"Q-{t}-{n}", input_root / t / f"{n}.kimu", "0" * 64,
                               NodeId[n], 538, 2151, (0, 21500000), "synthetic")
                    for t in TRAJECTORIES for n in ("A", "B"))
    protect_replay(output, anchors)


def _metric(metric: dict[str, Any]) -> str:
    value, unit = metric["value"], metric["unit"]
    if not metric["valid"] or value is None or not math.isfinite(value):
        display = f"unavailable ({metric['reason']})"
    else:
        display = f"{math.degrees(value):.6f} deg" if unit == "rad" else f"{value:.6f} {unit}"
    return (f"{display}; valid={str(metric['valid']).lower()}; reason={metric['reason']}; "
            f"evidence={metric['evidence_label']}; "
            f"anatomical_eligible={str(metric['anatomical_eligible']).lower()}")


def render_summary(replay: Path) -> str:
    """Read actual machine products, converting radians to degrees only for display."""
    manifest = _read(replay / "manifest.json")
    lines = ["# KineIMU Shoulder — complete sensor replay Demo", "",
             "M6 demo_passed=true. Four stored-Q trajectories completed under the frozen clean S/Q gates.", "",
             "Source type: synthetic; anatomical_eligible=false. Machine angles remain rad; "
             "display angles use deg = rad × 180/pi. Speed remains rad/s; durations s, boundaries us.", "",
             f"Processing: {manifest['processing_version']}; source HEAD: `{manifest['git_commit']}`; "
             f"tracked_dirty={str(manifest['tracked_dirty']).lower()}.", "",
             f"Runtime: `{json.dumps(manifest['runtime'], sort_keys=True)}`.", "",
             f"Input map SHA-256: `{manifest['input_digest_map_sha256']}`.", "",
             "Observed: decoded sensor/QC/time. Derived: calculated metrics. Assumed: known synthetic "
             "calibration/initialization/alignment/heading/clock. Validated: only the existing tested "
             "synthetic gate domain. Experimental: retained where emitted; labels are never promoted.", "",
             "The original [M5 report](replay/report.json) retains passed=false, CP4 OPEN and formal=false; "
             "its stage_passed=true describes this completed stored-Q stage.", "",
             "ROM uses the detected repetition boundaries; nominal full-motion 90 deg is not substituted. "
             "ROM sample SD uses ddof=1; CV is dimensionless; n<2 remains unavailable with a reason.", ""]
    for trajectory in TRAJECTORIES:
        folder = replay / f"cases/Q-{trajectory}"
        result = _read(folder / "result.json")
        derived = _read(folder / "derived.json.gz")
        processed = _read(folder / "processed.json.gz")
        summary = derived["summary"]
        keys = summary["comparability_keys"]
        definition = summary["definition_version"]
        lines += [f"## {trajectory} — {keys['exercise']} / {keys['side']}", "",
                  f"[Machine result](replay/cases/Q-{trajectory}/result.json); "
                  f"[derived](replay/cases/Q-{trajectory}/derived.json.gz); "
                  f"[processed](replay/cases/Q-{trajectory}/processed.json.gz).", "",
                  f"Counts (repetitions, Derived; definition={definition}; "
                  f"valid={str(summary['analysis_valid']).lower()}; reason={summary['reasons']}; "
                  "anatomical_eligible=false): " + "; ".join(
                      f"{name}={summary[name]}" for name in
                      ("detected_count", "valid_count", "excluded_count", "partial_start_count", "partial_end_count",
                       "interrupted_count", "proxy_valid_count", "proxy_unavailable_count")), "",
                  f"Truth/count comparison: `{json.dumps(result['counts'], sort_keys=True)}`. "
                  f"Coverage: `{json.dumps(result['coverage'], sort_keys=True)}`.", "",
                  f"Exclusion reasons: `{json.dumps(summary['exclusion_reason_counts'], sort_keys=True)}`.", "",
                  "| Node | Packets / samples | QC issues | Calibration / AHRS | Source SHA-256 |",
                  "|---|---|---|---|---|"]
        for node in ("A", "B"):
            row = processed["nodes"][node]
            qc = row["replay"]["qc"]
            lines.append(f"| {node} | {qc['packets_decoded']} / {qc['samples_decoded']} | {qc['issues']} | "
                         f"{row['calibration_executed']} / {row['ahrs_executed']} | "
                         f"`{row['replay']['source_sha256']}` |")
        lines += ["", "Eight core families: humerothoracic ROM; peak elevation; repetition count; "
                  "movement/phase duration; hold duration; angular velocity; rep-to-rep variability; "
                  "thorax compensation excursion proxy.", "",
                  f"Aggregate definition: `{definition}`. Each stratum retains its own denominator.", ""]

        def mean(name: str, *, stats: dict[str, Any] = summary["statistics"]) -> str:
            return " / ".join(f"n={group['n']}: {_metric(group['mean'])}"
                              for group in stats[name])

        lines += ["| Core family | Result |", "|---|---|",
                  f"| Humerothoracic ROM, mean | {mean('rom_rad')} |",
                  f"| Peak elevation, mean | {mean('peak_elevation_rad')} |",
                  f"| Repetition count | {summary['valid_count']} valid / {summary['detected_count']} detected; "
                  f"{summary['excluded_count']} excluded; Derived; valid={summary['analysis_valid']}; "
                  f"reason={summary['reasons']}; anatomical_eligible=false |",
                  f"| Movement / elevation / return duration | {mean('rep_duration_s')} / "
                  f"{mean('elevation_duration_s')} / {mean('return_duration_s')} |",
                  f"| Hold duration | {mean('hold_duration_s')} |",
                  f"| Angular velocity, mean / peak | {mean('rep_speed_mean_rads')} / "
                  f"{mean('rep_speed_max_rads')} |",
                  f"| Rep-to-rep variability, range / SD / CV (n={summary['valid_count']}) | "
                  f"{_metric(summary['rom_range'])} / {_metric(summary['rom_sd'])} / "
                  f"{_metric(summary['rom_cv'])} |",
                  f"| Thorax proxy magnitude, extension / lateral flexion / axial rotation | "
                  f"{mean('thorax_extension_magnitude_rad')} / {mean('thorax_lateral_flexion_magnitude_rad')} / "
                  f"{mean('thorax_axial_rotation_magnitude_rad')} |", "",
                  "<details>", "<summary>All metric strata, repetition phases, proxy extrema and gate errors</summary>",
                  "",
                  "| Metric | n | Mean | Maximum |", "|---|---:|---|---|"]
        for name, strata in sorted(summary["statistics"].items()):
            for group in strata:
                lines.append(f"| {name} | {group['n']} | {_metric(group['mean'])} | {_metric(group['maximum'])} |")
        lines += ["", "| Variability | Value |", "|---|---|"]
        for name in ("rom_range", "rom_sd", "rom_cv"):
            lines.append(f"| {name} (n={summary['valid_count']}) | {_metric(summary[name])} |")
        lines += ["", "Per-repetition phase support and validity (definition="
                  f"{keys['definition_version']}); all original boundaries and hold runs remain in machine data.", ""]
        for rep in derived["repetitions"]:
            candidate = rep["candidate"]
            lines.append(f"Rep {candidate['id']}: valid={candidate['valid']}, reason={candidate['reasons']}; "
                         f"start/peak/end_us={candidate['start_us']}/{candidate['peak_us']}/{candidate['end_us']}; "
                         f"rise={candidate['rise_support_us']}; return={candidate['return_support_us']}; "
                         f"hold_runs_us={rep['hold_runs_us']}; partial_start={candidate['partial_start']}; "
                         f"partial_end={candidate['partial_end']}; interrupted={candidate['interrupted']}.")
            lines += ["", "| Rep metric | Value |", "|---|---|"]
            for name, metric in sorted(rep["metrics"].items()):
                lines.append(f"| {name} | {_metric(metric)} |")
            lines.append("")
        lines += [f"Thorax proxy definition/policy: `{keys['proxy_policy']}`; "
                  "independent proxy denominator and heading/drift limits apply.", "",
                  "| Rep / component | Min / max / magnitude (deg) | Validity / evidence |",
                  "|---|---|---|"]
        for index, proxy in enumerate(derived["proxy"], 1):
            for name in ("extension", "lateral_flexion", "axial_rotation"):
                metric = proxy[name]
                values = " / ".join(_metric({**metric, "value": metric[k]})
                                    for k in ("min_rad", "max_rad", "magnitude_rad"))
                lines.append(f"| {index} / {name} | {values} | reasons={proxy['reasons']} |")
        lines += ["", "Independent error supports and unchanged gate budgets:", "",
                  "| Gate quantity | n | Maximum absolute error | RMSE | Tolerance | Gate |",
                  "|---|---:|---|---|---|---|"]
        for name, error in sorted(result["error_summary"].items()):
            lines.append(f"| {name} | {error['n']} | {error['max_abs_error']} {error['unit']} | "
                         f"{error['rmse']} {error['unit']} | {error['tolerance']} {error['unit']} | {error['gate']} |")
        lines += ["", "</details>", ""]
    lines += ["## Limits", "", *[f"- {limit}" for limit in LIMITATIONS], ""]
    return "\n".join(lines)


def _states(replay: Path, reason: str) -> list[dict[str, Any]]:
    rows = []
    for trajectory in TRAJECTORIES:
        path = replay / f"cases/Q-{trajectory}/result.json"
        row: dict[str, Any] = dict(id=f"Q-{trajectory}", disposition="NOT RUN", reason=reason, failed_gates=[])
        if path.exists():
            result = _read(path)
            disposition = result.get("stage_disposition", "FAILED")
            if disposition == "complete" and not result.get("passed"):
                disposition = "FAILED"
            row.update(disposition=disposition, reason=result.get("error", result.get("error_type", disposition)),
                       failed_gates=result.get("failed_gates", []), path=path.relative_to(replay).as_posix())
        rows.append(row)
    return rows


def _verify_replay(replay: Path, before: dict[str, str]) -> None:
    expected = {"manifest.json", "report.json"}
    expected |= {f"cases/Q-{t}/{name}" for t in TRAJECTORIES
                 for name in ("result.json", "processed.json.gz", "derived.json.gz", "annotations.json.gz",
                              "errors.json.gz")}
    hashes = _hashes(replay)
    if set(hashes) != expected | {"SHA256SUMS.txt"}:
        raise ValueError("incomplete or unexpected replay products")
    indexed = {}
    for line in (replay / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        if name not in expected or name in indexed or hashes[name] != digest:
            raise ValueError("replay checksum gate failed")
        indexed[name] = digest
    if set(indexed) != expected:
        raise ValueError("replay checksum inventory incomplete")
    report = _read(replay / "report.json")
    if (not report["stage_passed"] or report["case_count"] != 4 or report["failed_case_count"]
        or report["blocked_count"] or report["not_run_count"]
        or [r["id"] for r in report["results"]] != [f"Q-{t}" for t in TRAJECTORIES]):
        raise ValueError("four-trajectory report gate failed")
    for trajectory in TRAJECTORIES:
        folder = replay / f"cases/Q-{trajectory}"
        result = _read(folder / "result.json")
        if (not result["passed"] or result["failed_gates"] or result["stage_disposition"] != "complete"
            or result["input_audit"] != dict(before=before, after=before)):
            raise ValueError(f"case/input gate failed: {trajectory}")
        for name in ("processed", "derived", "annotations", "errors"):
            _read(folder / f"{name}.json.gz")


def run_demo(output: Path, *, input_root: Path = SAMPLE, command: list[str] | None = None) -> int:
    """Claim a new safe root; retain failed output and convert errors to strict exits."""
    started = datetime.now(UTC).isoformat()
    tick = time.perf_counter()
    claimed = False
    run: dict[str, Any] = dict(contract_id=CONTRACT, demo_passed=False, exit_code=1, disposition="FAILED",
                               command=command if command is not None else [sys.executable, *sys.argv],
                               output_absolute_path=str(output), input_root=str(input_root),
                               started_utc=started, ended_utc=None, duration_s=None, pid=os.getpid(),
                               source=None, runtime=None, input_sha256_before=None, input_sha256_after=None,
                               processing_version="m5-processing/1.1", metric_versions=None,
                               product_sha256={}, failed_gates=[], limitations=LIMITATIONS)
    code = 1
    phase = "preflight"
    try:
        output, input_root = output.resolve(), input_root.resolve()
        run.update(output_absolute_path=str(output), input_root=str(input_root))
        _protect(output, input_root)
        from kineimu_shoulder.validation.stored_demo import export_stored, input_audit

        run["input_sha256_before"] = input_audit(input_root)
        def git(*args: str) -> str:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        sources = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py"))
        sources += ["examples/m6_demo.py", "uv.lock", "docs/M6_DEMO_CONTRACT.md"]
        run["source"] = dict(head=git("rev-parse", "HEAD"),
                             tracked_dirty=bool(git("status", "--porcelain", "--untracked-files=no")),
                             file_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sources})
        run["runtime"] = dict(python=platform.python_version(), platform=platform.platform(),
                              packages={name: version(name) for name in ("numpy", "scipy", "imufusion", "imucal")},
                              thread_environment={name: os.environ.get(name) for name in
                                                  ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")})
        # Check guards again immediately before the exclusive directory claim.
        _protect(output, input_root)
        output.mkdir(parents=True, exist_ok=False)
        claimed = True
        phase = "processing"
        code = export_stored(output / "replay", input_root=input_root)
        run["input_sha256_after"] = input_audit(input_root)
        states = _states(output / "replay", "exporter did not execute this trajectory")
        run["trajectories"] = states
        if any(row["disposition"] == "FAILED" for row in states):
            code = 1
        if run["input_sha256_before"] != run["input_sha256_after"]:
            code = 1
            run["failed_gates"].append("immutable_input")
        if code == 0:
            phase = "verification"
            _verify_replay(output / "replay", run["input_sha256_before"])
            phase = "presentation"
            _write(output / "summary.md", render_summary(output / "replay").encode("utf-8"))
            summary = _read(output / "replay/cases/Q-F90/derived.json.gz")["summary"]
            keys = summary["comparability_keys"]
            run["metric_versions"] = dict(summary=summary["definition_version"],
                                           kinematics_exercise=keys["definition_version"],
                                           thorax=keys["proxy_policy"][:3],
                                           thresholds=keys["configuration"]["version"])
    except Exception as exc:
        code = 2 if isinstance(exc, (ModuleNotFoundError, PackageNotFoundError, PermissionError)) or (
            phase in ("preflight", "processing") and isinstance(exc, FileNotFoundError)) else 1
        run["failed_gates"].append(f"{phase}:{type(exc).__name__}:{exc}")
    if claimed:
        # Unavailable post-run evidence must not prevent writing the failure record.
        try:
            if run["input_sha256_after"] is None:
                from kineimu_shoulder.validation.stored_demo import input_audit

                run["input_sha256_after"] = input_audit(input_root)
        except Exception as exc:
            if code != 1:
                code = 2 if isinstance(exc, (FileNotFoundError, PermissionError)) else 1
            run["failed_gates"].append(f"post_input_audit:{type(exc).__name__}:{exc}")
        try:
            run["trajectories"] = _states(output / "replay", "execution stopped before a result was produced")
            if any(row["disposition"] == "FAILED" for row in run["trajectories"]):
                code = 1
            for row in run["trajectories"]:
                run["failed_gates"] += [f"{row['id']}:{gate}" for gate in row["failed_gates"]]
            run.update(demo_passed=code == 0, exit_code=code,
                       disposition="complete" if code == 0 else "FAILED" if code == 1 else "BLOCKED",
                       ended_utc=datetime.now(UTC).isoformat(), duration_s=time.perf_counter() - tick,
                       product_sha256=_hashes(output))
            content = _json(run)
            hashes = _hashes(output)
            hashes["run.json"] = sha256(content).hexdigest()
            _write(output / "SHA256SUMS.txt",
                   "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode())
            # Success metadata is published only after the complete index write succeeds.
            _write(output / "run.json", content)
        except Exception as exc:
            code = 1
            run["failed_gates"].append(f"finalization:{type(exc).__name__}:{exc}")
    if code == 0:
        print(f"Four trajectories complete; summary: {output / 'summary.md'}; synthetic, anatomical_eligible=false.")
    else:
        print(f"{'FAILED' if code == 1 else 'BLOCKED'}: {run['failed_gates'] or run.get('trajectories')}; "
              f"{'retained root' if claimed else 'no root created'}: {output}", file=sys.stderr)
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description="KineIMU Shoulder: complete hardware-free stored sensor replay.")
    parser.add_argument("--output", type=Path, required=True, help="new output directory; never overwritten")
    args = parser.parse_args()
    raise SystemExit(run_demo(args.output, command=list(sys.orig_argv)))
