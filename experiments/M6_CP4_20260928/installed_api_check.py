"""Analytical API checks executed with -I outside the checkout in a new venv."""

import hashlib
import importlib.metadata as metadata
import json
import sys
from math import cos, pi, sin
from pathlib import Path

import numpy as np
from imucal import FerrarisCalibrationInfo

import kineimu_shoulder
from kineimu_shoulder.frames import rotate_vector
from kineimu_shoulder.orientation import estimate_orientation
from kineimu_shoulder.relative_orientation import ClockMap, HeadingRelation, RelativeOrientationResult
from kineimu_shoulder.shoulder import AlignmentRecord, long_axis_elevation


def main() -> None:
    source_root = Path(sys.argv[1]).resolve()
    prefix = Path(sys.prefix).resolve()
    imported = Path(kineimu_shoulder.__file__).resolve()
    assert imported.is_relative_to(prefix) and not imported.is_relative_to(source_root)
    assert sys.flags.isolated and (imported.parent / "py.typed").is_file()
    assert kineimu_shoulder.__version__ == "0.1.0"
    distribution = metadata.distribution("kineimu_shoulder")
    root_notices = {}
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        member = next(
            p for p in distribution.files
            if str(p).replace("\\", "/").endswith(f".dist-info/licenses/{name}")
        )
        data = Path(distribution.locate_file(member)).read_bytes()
        assert data == (source_root / name).read_bytes()
        root_notices[name] = hashlib.sha256(data).hexdigest()
    versions = {name: metadata.version(name) for name in (
        "kineimu_shoulder", "numpy", "pandas", "scipy", "imucal", "imufusion", "python-dateutil", "six", "tzdata"
    )}
    assert versions == {
        "kineimu_shoulder": "0.1.0", "numpy": "2.5.2", "pandas": "3.0.5", "scipy": "1.18.1",
        "imucal": "2.6.0", "imufusion": "1.3.3", "python-dateutil": "2.9.0.post0",
        "six": "1.17.0", "tzdata": "2026.3",
    }
    identity, zeros = np.eye(3), np.zeros((2, 3))
    calibration = FerrarisCalibrationInfo(
        acc_unit="m/s^2", gyr_unit="rad/s", from_acc_unit="m/s^2", from_gyr_unit="rad/s",
        K_a=identity, R_a=identity, b_a=np.zeros(3), K_g=identity, R_g=identity,
        K_ga=np.zeros((3, 3)), b_g=np.zeros(3),
    )
    acceleration, rate = calibration.calibrate(zeros, zeros, "m/s^2", "rad/s")
    # Analytical source: an identity affine calibration maps zero vectors to zero.
    np.testing.assert_array_equal(acceleration, zeros)
    np.testing.assert_array_equal(rate, zeros)
    assert FerrarisCalibrationInfo.from_json(calibration.to_json()) == calibration
    time = np.array([0, 5_000, 20_000, 40_000, 60_000], dtype=np.int64)
    ahrs = estimate_orientation(time, np.tile([0.0, 0.0, 9.80665], (5, 1)),
                                np.tile([0.0, 0.0, pi / 2], (5, 1)), max_gap_s=0.03)
    # Analytical source: +Z constant pi/2 rad/s over 0.06 s, M2 observed-dt fixture.
    angle = pi / 2 * 0.06
    np.testing.assert_allclose(ahrs.quaternion_wn[-1], [cos(angle / 2), 0, 0, sin(angle / 2)],
                               rtol=0, atol=2e-5)
    assert not ahrs.heading_observable
    # Analytical source: active Ry(pi/2) maps upper-arm +Z to thorax +X.
    q = (cos(pi / 4), 0.0, sin(pi / 4), 0.0)
    np.testing.assert_allclose(rotate_vector(q, [0, 0, 1]), [1, 0, 0], rtol=0, atol=1e-12)
    sha_a, sha_b = "a" * 64, "b" * 64
    clocks = [ClockMap(node, f"clock-{node}", 0, 1, 0, 0, 2_000_000, 0, 2_000_000,
                       1, 1, "synthetic anchors", sha, "supported")
              for node, sha in (("A", sha_a), ("B", sha_b))]
    relative = RelativeOrientationResult(
        np.array([0], dtype=np.int64), np.array([q]), np.array([True]), ("valid",), "Derived", "slerp",
        500_000, 10, sha_a, sha_b, clocks[0], clocks[1],
        HeadingRelation("world-A", "world-B", (1, 0, 0, 0), "synthetic shared heading", sha_a, "supported"),
    )
    alignments = [AlignmentRecord(
        node, 0, segment, "right", (1, 0, 0, 0), f"synthetic-{node}", "known synthetic axes", sha,
        "arms down; H +Z proximal", "current", "same unchanged synthetic mount and source epoch",
        False, "exact synthetic ground truth", "supported", "synthetic_ground_truth",
    ) for node, segment, sha in (("A", "T", sha_a), ("B", "H", sha_b))]
    elevation = long_axis_elevation(relative, thorax_alignment=alignments[0], humerus_alignment=alignments[1],
                                   side="right", source_type="synthetic", max_sample_gap_us=500_000)
    # Analytical source: orthogonal long axes yield pi/2 elevation (M3 E1 fixture).
    np.testing.assert_allclose(elevation.elevation_rad, [pi / 2], rtol=0, atol=1e-10)
    assert elevation.valid.tolist() == [True] and not elevation.anatomical_eligible
    missing = long_axis_elevation(relative, thorax_alignment=None, humerus_alignment=None,
                                 side="right", source_type="recorded", max_sample_gap_us=500_000)
    assert missing.valid.tolist() == [False] and np.isnan(missing.elevation_rad[0])
    assert not missing.anatomical_eligible
    snapshot = prefix / "share/kineimu-shoulder/third-party"
    verified = {}
    for original in (source_root / "docs/release/licenses").rglob("*"):
        if original.is_file():
            name = original.relative_to(source_root / "docs/release/licenses")
            data = (snapshot / name).read_bytes()
            assert data == original.read_bytes()
            verified[name.as_posix()] = hashlib.sha256(data).hexdigest()
    print(json.dumps({
        "status": "PASS", "isolated": bool(sys.flags.isolated), "cwd": str(Path.cwd()),
        "prefix": str(prefix), "python": sys.version, "imported_package": str(imported),
        "versions": versions, "notice_files_verified": verified, "root_notice_sha256": root_notices,
        "checks": ["identity SI calibration", "observed-dt AHRS", "active rotation", "M3 pi/2 elevation",
                   "missing alignment remains invalid", "synthetic anatomical eligibility false", "installed notices"],
    }, indent=2))


if __name__ == "__main__":
    main()
