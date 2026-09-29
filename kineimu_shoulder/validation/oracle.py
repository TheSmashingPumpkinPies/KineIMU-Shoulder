"""Independent scalar/matrix/integer-time M5 oracle (O/F/T).

Imports parameter records only. No generator, SciPy or production geometry/metric
helpers. Body rate is checked by a matrix derivative, never generator's formula.
"""

from fractions import Fraction
from math import asin, atan2, ceil, cos, pi, sin
from typing import Any

import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.validation.motions import MOTIONS, Cycle

FloatArray = NDArray[np.float64]


def _angle(trajectory: str, t: float) -> float:
    start = 5.0
    for cycle in MOTIONS[trajectory].cycles:
        rise, hold, fall, rest = (v / 1e6 for v in (cycle.rise_us, cycle.hold_us, cycle.return_us, cycle.rest_us))
        u = t - start
        if 0 < u <= rise:
            return cycle.peak_deg * pi / 180 * u / rise
        if rise < u <= rise + hold:
            return cycle.peak_deg * pi / 180
        if rise + hold < u <= rise + hold + fall:
            return cycle.peak_deg * pi / 180 * (1 - (u - rise - hold) / fall)
        start += rise + hold + fall + rest
    return 0.0


def _rx(a: float) -> FloatArray:
    return np.array([[1, 0, 0], [0, cos(a), -sin(a)], [0, sin(a), cos(a)]], dtype=np.float64)


def _ry(b: float) -> FloatArray:
    return np.array([[cos(b), 0, sin(b)], [0, 1, 0], [-sin(b), 0, cos(b)]], dtype=np.float64)


def _rz(c: float) -> FloatArray:
    return np.array([[cos(c), -sin(c), 0], [sin(c), cos(c), 0], [0, 0, 1]], dtype=np.float64)


def segment_matrix(trajectory: str, node: str, t: float) -> FloatArray:
    """T1 explicit ZYX entries, followed by independently declared relative rotation."""
    motion = MOTIONS[trajectory]
    e = _angle(trajectory, t)
    a = e / 30 if motion.thorax == "mixed" else 0
    b = -e / 9 if motion.thorax != "fixed" else 0
    c = e / 18 if motion.thorax == "mixed" else 0
    sa, ca, sb, cb, sc, cc = sin(a), cos(a), sin(b), cos(b), sin(c), cos(c)
    thorax = np.array(
        [
            [cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa],
            [sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa],
            [-sb, cb * sa, cb * ca],
        ]
    )
    relative = _rx(motion.sign * e) if motion.axis == "X" else _ry(motion.sign * e)
    return thorax if node == "A" else thorax @ relative


def _sensor_matrix(trajectory: str, node: str, t: float) -> FloatArray:
    ns = _rz(pi / 2) if node == "A" else _rx(-pi / 2)
    nk = _rx(pi / 2) if node == "A" else _ry(pi / 2)
    return segment_matrix(trajectory, node, t) @ nk.T @ ns


def sensor_reference(trajectory: str, node: str, t: float) -> tuple[FloatArray, FloatArray, FloatArray]:
    """O5 numerical matrix derivative at h=1e-5s; LEFT derivative at knots."""
    r = _sensor_matrix(trajectory, node, t)
    knots = {0.0, 5.0}
    current = 5.0
    for cycle in MOTIONS[trajectory].cycles:
        for duration in (cycle.rise_us, cycle.hold_us, cycle.return_us, cycle.rest_us):
            current += duration / 1e6
            knots.add(current)
    h = 1e-5
    if any(abs(t - knot) < 1e-10 for knot in knots):
        derivative = (
            3 * r - 4 * _sensor_matrix(trajectory, node, t - h) + _sensor_matrix(trajectory, node, t - 2 * h)
        ) / (2 * h)
    else:
        derivative = (_sensor_matrix(trajectory, node, t + h) - _sensor_matrix(trajectory, node, t - h)) / (2 * h)
    skew = r.T @ derivative
    omega = np.array([skew[2, 1] - skew[1, 2], skew[0, 2] - skew[2, 0], skew[1, 0] - skew[0, 1]]) / 2
    return r.T @ np.array([0, 0, 9.80665]), omega, r


def labels(trajectory: str, *, step_us: int = 10000) -> list[dict[str, Any]]:
    """Independent rational ceil crossings; physical support and nominal M4 distinct."""
    motion = MOTIONS[trajectory]
    start = 5_000_000
    rows: list[dict[str, Any]] = []
    analysis_end = motion.analysis_end_us or motion.end_us
    for index, c in enumerate(motion.cycles):
        ks = ceil(Fraction(c.rise_us * 20, c.peak_deg * step_us))
        kr = ceil(Fraction(c.return_us * (c.peak_deg - 10), c.peak_deg * step_us))
        begin = start + ks * step_us
        peak = start + c.rise_us
        end = peak + c.hold_us + kr * step_us
        e0 = Fraction(c.peak_deg * ks * step_us, c.rise_us)
        e1 = Fraction(c.peak_deg) * (1 - Fraction(kr * step_us, c.return_us))
        physical_end = start + c.rise_us + c.hold_us + c.return_us
        complete = start >= motion.analysis_start_us and physical_end <= analysis_end
        eligible = complete and trajectory != "WRONG"
        hold = c.hold_us if c.hold_us >= 500000 else 0
        rows.append(
            {
                "truth_id": f"{trajectory}:rep-{index + 1}",
                "physical_start_us": start,
                "physical_end_us": physical_end,
                "complete": complete,
                "eligible": eligible,
                "start_us": begin,
                "peak_us": peak,
                "end_us": end,
                "confirm_start_us": begin + 200000,
                "confirm_end_us": end + 200000,
                "plateau_support_us": [peak, peak + c.hold_us],
                "peak_rad": c.peak_deg * pi / 180,
                "rom_rad": float(c.peak_deg - min(e0, e1)) * pi / 180,
                "duration_s": (end - begin) / 1e6,
                "rise_s": (peak - begin) / 1e6,
                "hold_s": hold / 1e6,
                "return_s": (end - peak - hold) / 1e6,
                "mean_speed_rads": float((2 * c.peak_deg - e0 - e1) / Fraction(end - begin, 1000000)) * pi / 180,
                "max_speed_rads": max(c.peak_deg * 1e6 / c.rise_us, c.peak_deg * 1e6 / c.return_us) * pi / 180,
                "expected_exclusion": "plane_mismatch"
                if trajectory == "WRONG"
                else "partial_start"
                if start < motion.analysis_start_us
                else "partial_end"
                if physical_end > analysis_end
                else None,
            }
        )
        start = physical_end + c.rest_us
    return rows


def observation_labels(trajectory: str, times_us: list[int]) -> list[dict[str, Any]]:
    """Physical reference sampled on a supplied observation grid, without bridging loss.

    These are analytical envelope labels, not a segmentation/QC prediction. Missing
    crossings/supports yield explicit nulls; nominal labels are never overwritten.
    """
    if any(b <= a for a, b in zip(times_us, times_us[1:], strict=False)):
        raise ValueError("oracle observation times must increase strictly")
    result = []
    for nominal, cycle in zip(labels(trajectory), MOTIONS[trajectory].cycles, strict=True):
        start = nominal["physical_start_us"]
        peak = start + cycle.rise_us
        plateau_end = peak + cycle.hold_us
        physical_end = nominal["physical_end_us"]
        support = [t for t in times_us if start <= t <= physical_end]

        def degrees(
            t: int, peak: int = peak, start: int = start, plateau_end: int = plateau_end, cycle: Cycle = cycle
        ) -> Fraction:
            if t <= peak:
                return Fraction(cycle.peak_deg * (t - start), cycle.rise_us)
            if t <= plateau_end:
                return Fraction(cycle.peak_deg)
            return Fraction(cycle.peak_deg) * (1 - Fraction(t - plateau_end, cycle.return_us))

        rises = [t for t in support if t <= peak and degrees(t) >= 20]
        falls = [t for t in support if t >= plateau_end and degrees(t) <= 10]
        values = [degrees(t) for t in support]
        observed = {
            "truth_id": nominal["truth_id"],
            "label_type": "observation-grid",
            "start_us": rises[0] if rises else None,
            "end_us": falls[0] if falls else None,
            "peak_us": support[values.index(max(values))] if values else None,
            "peak_rad": float(max(values)) * pi / 180 if values else None,
            "valid": bool(rises and falls and values),
            "reason": None if rises and falls and values else "missing_observation_support",
        }
        result.append(observed)
    return result


def summary(trajectory: str) -> dict[str, Any]:
    """F4/U1 scalar n-1 SD/CV, active cadence, rest and eligible-count reference."""
    reps = [r for r in labels(trajectory) if r["eligible"]]
    values = [r["rom_rad"] for r in reps]
    n = len(values)
    mean = sum(values) / n if n else None
    sd = (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5 if n >= 2 and mean is not None else None
    active = sum(r["duration_s"] for r in reps)
    rests = [(b["start_us"] - a["end_us"]) / 1e6 for a, b in zip(reps, reps[1:], strict=False)]
    return {
        "valid_count": n,
        "physical_count": len(MOTIONS[trajectory].cycles),
        "rom_mean_rad": mean,
        "rom_max_rad": max(values) if values else None,
        "rom_range_rad": max(values) - min(values) if values else None,
        "rom_sd_rad": sd,
        "rom_cv": sd / mean if sd is not None and mean is not None and mean > 1e-12 else None,
        "active_s": active if n else None,
        "cadence_per_s": n / active if active else None,
        "rest_s": rests,
    }


def proxy(trajectory: str, start_us: int, times_us: list[int]) -> FloatArray:
    """T0/T1 excursion from movement-start matrix, with no Euler subtraction."""
    baseline = segment_matrix(trajectory, "A", start_us / 1e6)
    output = []
    for t in times_us:
        d = baseline.T @ segment_matrix(trajectory, "A", t / 1e6)
        output.append([-asin(float(np.clip(-d[2, 0], -1, 1))), -atan2(d[2, 1], d[2, 2]), atan2(d[1, 0], d[0, 0])])
    return np.asarray(output, dtype=np.float64)
