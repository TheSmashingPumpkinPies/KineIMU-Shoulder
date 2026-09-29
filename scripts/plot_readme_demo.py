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

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("F90", "Left flexion"),
    ("AL90", "Left abduction"),
    ("AR90", "Right abduction"),
    ("T-MIX", "Left flexion / moving thorax"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True, help="completed M6 output directory")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/assets")
    args = parser.parse_args()
    run = json.loads((args.demo / "run.json").read_bytes())
    if not run["demo_passed"] or run["input_sha256_before"] != run["input_sha256_after"]:
        raise ValueError("requires a successful M6 run with unchanged inputs")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    fig.patch.set_facecolor("#f8fafc")
    fig.suptitle("KineIMU Shoulder | synthetic motion replay", x=0.07, ha="left",
                 fontsize=20, fontweight="bold", color="#0f172a")
    fig.text(0.07, 0.905, "Stored dual-IMU observations → replay-derived humerothoracic elevation",
             fontsize=12, color="#475569")
    provenance = {"source_type": "synthetic", "anatomical_eligible": False,
                  "source_commit": run["source"]["head"], "runtime": run["runtime"],
                  "input_sha256": run["input_sha256_before"], "products": {},
                  "plot": {"matplotlib": matplotlib.__version__, "numpy": np.__version__,
                           "angle_conversion": "deg = rad * 180 / pi", "smoothing": False}}
    for ax, (case, title) in zip(axes.flat, CASES, strict=True):
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
    fig.text(0.07, 0.035, "synthetic · anatomical_eligible=false · constructed calibration, heading and clocks\n"
             "Source: datasets/samples/m6_synthetic/*.kimu via M6 replay · no human or clinical validation",
             fontsize=10, color="#475569", linespacing=1.6)
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.18, top=0.82, hspace=0.5, wspace=0.22)
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "synthetic-motion.png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    (args.output / "synthetic-motion.provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
