"""Plot actual M6 replay products; never regenerate or modify synthetic inputs."""

from __future__ import annotations

import argparse
import gzip
import json
from hashlib import sha256
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("F90", "Left flexion"),
    ("AL90", "Left abduction"),
    ("AR90", "Right abduction"),
    ("T-MIX", "Left flexion / moving thorax"),
)


def thorax_components(data, derived):
    """Reproduce M4 movement-start components and cross-check stored extrema."""
    trace = data["trace"]
    times = np.asarray(trace["common_time_us"])
    values = np.full((len(times), 3), np.nan)
    names = ("extension", "lateral_flexion", "axial_rotation")
    for rep, proxy in zip(derived["repetitions"], derived["proxy"], strict=True):
        candidate = rep["candidate"]
        if not candidate["valid"] or not all(proxy[name]["valid"] for name in names):
            continue
        start, end = np.searchsorted(times, [candidate["start_us"], candidate["end_us"]])
        if not all(trace["valid"][start:end + 1]):
            raise ValueError("invalid thorax samples within valid repetition")
        rotations = Rotation.from_quat(np.asarray(trace["quaternion_wat"])[start:end + 1], scalar_first=True)
        matrices = (rotations[0].inv() * rotations).as_matrix()
        cos_beta = np.hypot(matrices[:, 0, 0], matrices[:, 1, 0])
        if np.any(cos_beta <= trace["configuration"]["decomposition_cos_floor"]):
            raise ValueError("singular thorax decomposition")
        beta = np.arctan2(-matrices[:, 2, 0], cos_beta)
        alpha = (np.arctan2(matrices[:, 2, 1], matrices[:, 2, 2]) + np.pi) % (2 * np.pi) - np.pi
        gamma = (np.arctan2(matrices[:, 1, 0], matrices[:, 0, 0]) + np.pi) % (2 * np.pi) - np.pi
        components = np.column_stack((-beta, -alpha, gamma))
        components[0] = 0.
        for column, name in enumerate(names):
            np.testing.assert_allclose(
                [components[:, column].min(), components[:, column].max()],
                [proxy[name]["min_rad"], proxy[name]["max_rad"]], rtol=0, atol=1e-10)
        values[start:end + 1] = components
    return times / 1e6, np.rad2deg(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True, help="completed M6 output directory")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/assets")
    args = parser.parse_args()
    run = json.loads((args.demo / "run.json").read_bytes())
    if not run["demo_passed"] or run["input_sha256_before"] != run["input_sha256_after"]:
        raise ValueError("requires a successful M6 run with unchanged inputs")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(12, 10.5))
    grid = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.25])
    axes = [fig.add_subplot(grid[row, col]) for row in range(2) for col in range(2)]
    thorax_ax = fig.add_subplot(grid[2, :])
    fig.patch.set_facecolor("#f8fafc")
    fig.suptitle("KineIMU Shoulder | synthetic motion replay", x=0.07, ha="left",
                 fontsize=20, fontweight="bold", color="#0f172a")
    fig.text(0.07, 0.93, "Same relative arm motion; different motion planes and thorax movement",
             fontsize=12, color="#475569")
    provenance = {"source_type": "synthetic", "anatomical_eligible": False,
                  "source_commit": run["source"]["head"], "runtime": run["runtime"],
                  "input_sha256": run["input_sha256_before"], "products": {},
                  "plot": {"matplotlib": matplotlib.__version__, "numpy": np.__version__,
                           "angle_conversion": "deg = rad * 180 / pi", "smoothing": False,
                           "thorax_reference": "each detected repetition start; M4 Z-Y-X (-beta, -alpha, gamma)",
                           "thorax_extrema_check_atol_rad": 1e-10}}
    for ax, (case, title) in zip(axes, CASES, strict=True):
        products = {}
        for name in ("processed.json.gz", "derived.json.gz"):
            relative = f"replay/cases/Q-{case}/{name}"
            content = (args.demo / relative).read_bytes()
            digest = sha256(content).hexdigest()
            if digest != run["product_sha256"][relative]:
                raise ValueError(f"changed demo product: {relative}")
            provenance["products"][relative] = digest
            products[name] = json.loads(gzip.decompress(content))
        data = products["processed.json.gz"]
        summary = products["derived.json.gz"]["summary"]
        if case in ("F90", "T-MIX"):
            thorax_time, components = thorax_components(data, products["derived.json.gz"])
            if case == "F90":
                np.testing.assert_allclose(components[np.isfinite(components)], 0., rtol=0, atol=1e-10)
                thorax_ax.plot(thorax_time, components[:, 0], color="#64748b", linestyle="--",
                               linewidth=1.5, label="F90 fixed thorax (all components = 0)")
            else:
                for column, (label, color, style) in enumerate((
                    ("T-MIX extension", "#c05621", "-"),
                    ("T-MIX lateral flexion", "#6d28d9", "--"),
                    ("T-MIX axial rotation", "#0369a1", "-."),
                )):
                    thorax_ax.plot(thorax_time, components[:, column], color=color,
                                   linestyle=style, linewidth=2, label=label)
        time = np.asarray(data["relative"]["common_time_us"]) / 1e6
        elevation = np.rad2deg(np.asarray(data["elevation"], dtype=float))
        valid = np.asarray(data["elevation_valid"], dtype=bool)
        if not (time.shape == elevation.shape == valid.shape):
            raise ValueError(f"unaligned arrays: {case}")
        elevation[~valid] = np.nan  # Preserve invalid gaps; never connect through them.
        ax.plot(time, elevation, color="#007f86", linewidth=2.2)
        ax.set_title(f"{case} · {title}", loc="left", fontsize=12, fontweight="bold", pad=12)
        ax.text(0.97, 0.9, f"{summary['valid_count']} valid repetitions", transform=ax.transAxes,
                ha="right", color="#475569", fontsize=10)
        ax.set_xlim(*[v / 1e6 for v in data["evaluation_window_us"]])
        ax.set_ylim(-5, 105)
        ax.set_yticks([0, 30, 60, 90])
        ax.set_xticks([5, 10, 15, 20])
        ax.grid(axis="y", color="#dce3eb", linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["bottom", "left"]].set_color("#cbd5e1")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Elevation (deg)")
    thorax_ax.set_title("T-MIX · Thorax movement is visible on its own scale", loc="left",
                        fontsize=13, fontweight="bold", pad=42)
    thorax_ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, frameon=False, fontsize=10)
    thorax_ax.set(xlim=(5, 21.5), ylim=(-4, 10), xlabel="Time (s)",
                  ylabel="Thorax excursion (deg)", xticks=[5, 10, 15, 20], yticks=[-3, 0, 3, 6, 9])
    thorax_ax.grid(axis="y", color="#dce3eb", linewidth=0.8)
    thorax_ax.spines[["top", "right"]].set_visible(False)
    thorax_ax.spines[["bottom", "left"]].set_color("#cbd5e1")
    fig.text(0.07, 0.084, "Thorax proxy: zeroed at each detected repetition start; "
             "gaps between repetitions are not plotted.",
             fontsize=10, color="#475569")
    fig.text(0.07, 0.025, "synthetic · anatomical_eligible=false · constructed calibration, heading and clocks\n"
             "Source: datasets/samples/m6_synthetic/*.kimu via M6 replay · no human or clinical validation",
             fontsize=10, color="#475569", linespacing=1.6)
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.15, top=0.865, hspace=0.85, wspace=0.22)
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "synthetic-motion.png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    (args.output / "synthetic-motion.provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
