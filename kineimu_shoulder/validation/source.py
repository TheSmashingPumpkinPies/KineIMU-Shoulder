"""M5 sensor source: SciPy rotations and analytic body rates, independent of oracle.

Ideal zero-translation/zero-lever-arm force model; synthetic heading/initial pose.
All arrays retain original indices; no interpolation, filtering or hidden resampling.
"""

from dataclasses import dataclass
from math import pi

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SampleFlags,
    SamplePacket,
)
from kineimu_shoulder.validation.motions import MOTIONS

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]
G = 9.80665
ACCEL_LSB = 0.122e-3 * G
GYRO_LSB = 17.5e-3 * pi / 180


@dataclass(frozen=True)
class Perturbation:
    seed: int = 0
    target: str = "SAME"
    accel_sigma: float = 0
    gyro_sigma: float = 0
    bias_rads: float = 0
    ramp_rads: float = 0
    sample_jitter_us: int = 0
    timestamp_jitter_us: int = 0
    loss: str = "none"
    clock_ppm: float = 0
    clock_enabled: bool = False
    heading_rate_rads: float = 0
    heading_path: str = "sensor"
    calibration: bool = False

    def __post_init__(self) -> None:
        if self.target not in ("A", "B", "SAME", "DIFF"):
            raise ValueError("unknown target")
        if self.heading_path not in ("sensor", "world"):
            raise ValueError("unknown heading mechanism")
        if self.loss not in (
            "none",
            "sample-one",
            "sample-per",
            "sample-burst",
            "packet-one",
            "packet-per",
            "packet-burst",
        ):
            raise ValueError("unknown loss mask")
        values = (
            self.accel_sigma,
            self.gyro_sigma,
            self.bias_rads,
            self.ramp_rads,
            self.clock_ppm,
            self.heading_rate_rads,
        )
        if not all(np.isfinite(v) for v in values) or self.accel_sigma < 0 or self.gyro_sigma < 0:
            raise ValueError("perturbation values must be finite; sigma nonnegative")
        if self.seed < 0 or self.sample_jitter_us < 0 or self.timestamp_jitter_us < 0 or self.clock_ppm <= -1e6:
            raise ValueError("invalid seed, jitter or clock scale")


@dataclass(frozen=True)
class NodeSource:
    sequence: IntArray
    nominal_time_us: IntArray
    true_time_us: IntArray
    claimed_time_us: IntArray
    device_time_us: IntArray
    force_mps2: FloatArray
    rate_rads: FloatArray
    q_ws: FloatArray
    q_wk: FloatArray
    q_wn: FloatArray
    r_ns: FloatArray
    r_nk: FloatArray
    retained_mask: BoolArray
    clock_scale: float
    clock_offset_us: float
    clock_rounding_residual_us: FloatArray


@dataclass(frozen=True)
class DualSource:
    trajectory: str
    perturbation: Perturbation
    nodes: dict[str, NodeSource]
    sample_hz: int
    source_type: str = "synthetic"
    anatomical_eligible: bool = False


def _profile(trajectory: str, times: FloatArray) -> tuple[FloatArray, FloatArray]:
    motion = MOTIONS[trajectory]
    angle = np.zeros(len(times))
    rate = np.zeros(len(times))
    start = 5.0
    for cycle in motion.cycles:
        rise, hold, fall, rest = np.array([cycle.rise_us, cycle.hold_us, cycle.return_us, cycle.rest_us]) / 1e6
        peak = cycle.peak_deg * pi / 180
        u = times - start
        rising = (u > 0) & (u <= rise)
        plateau = (u > rise) & (u <= rise + hold)
        falling = (u > rise + hold) & (u <= rise + hold + fall)
        angle[rising] = peak * u[rising] / rise
        rate[rising] = peak / rise
        angle[plateau] = peak
        angle[falling] = peak * (1 - (u[falling] - rise - hold) / fall)
        rate[falling] = -peak / fall
        start += rise + hold + fall + rest
    return angle, rate


def _geometry(
    trajectory: str, node: str, times: FloatArray, identity_axes: bool = False
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    e, ed = _profile(trajectory, times)
    motion = MOTIONS[trajectory]
    n = len(times)
    a = e / 30 if motion.thorax == "mixed" else np.zeros(n)
    b = -e / 9 if motion.thorax != "fixed" else np.zeros(n)
    c = e / 18 if motion.thorax == "mixed" else np.zeros(n)
    ad = ed / 30 if motion.thorax == "mixed" else np.zeros(n)
    bd = -ed / 9 if motion.thorax != "fixed" else np.zeros(n)
    cd = ed / 18 if motion.thorax == "mixed" else np.zeros(n)
    thorax = Rotation.from_euler("ZYX", np.column_stack([c, b, a]))
    wt = np.column_stack(
        [ad - cd * np.sin(b), bd * np.cos(a) + cd * np.sin(a) * np.cos(b), -bd * np.sin(a) + cd * np.cos(a) * np.cos(b)]
    )
    relative = Rotation.from_euler(motion.axis, (motion.sign * e)[:, None])
    wr = np.zeros((n, 3))
    wr[:, 0 if motion.axis == "X" else 1] = motion.sign * ed
    segment = thorax if node == "A" else thorax * relative
    body = wt if node == "A" else relative.inv().apply(wt) + wr
    ns = Rotation.from_euler("Z", pi / 2) if node == "A" else Rotation.from_euler("X", -pi / 2)
    nk = Rotation.from_euler("X", pi / 2) if node == "A" else Rotation.from_euler("Y", pi / 2)
    if identity_axes:
        ns = nk = Rotation.identity()
    node_rotation = segment * nk.inv()
    sensor = node_rotation * ns
    force = sensor.inv().apply(np.tile([0, 0, G], (n, 1)))
    gyro = (ns.inv() * nk).apply(body)
    return (
        force,
        gyro,
        sensor.as_quat(scalar_first=True),
        segment.as_quat(scalar_first=True),
        ns.as_matrix(),
        nk.as_matrix(),
    )


def _rng(seed: int, node: str, factor: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 1 if node == "A" else 2, factor])))


def generate(
    trajectory: str, perturbation: Perturbation | None = None, *, sample_hz: int = 100, identity_axes: bool = False
) -> DualSource:
    """Create full original streams then apply loss; arrays are read-only."""
    if trajectory not in MOTIONS or sample_hz not in (100, 200):
        raise ValueError("unknown trajectory or unsupported sample rate")
    perturbation = perturbation or Perturbation()
    motion = MOTIONS[trajectory]
    nominal = np.arange(0, motion.end_us + 1, 1_000_000 // sample_hz, dtype=np.int64)
    n = len(nominal)
    knots = {0, motion.end_us, 5_000_000}
    start = 5_000_000
    for cycle in motion.cycles:
        for duration in (cycle.rise_us, cycle.hold_us, cycle.return_us, cycle.rest_us):
            start += duration
            knots.add(start)
    nodes = {}
    for node in ("A", "B"):
        p = perturbation
        affected = p.target in (node, "SAME", "DIFF")
        sign = -1 if p.target == "DIFF" and node == "B" else 1
        true = nominal.copy()
        claimed = nominal.copy()
        for factor, jitter, array in ((21, p.sample_jitter_us, true), (22, p.timestamp_jitter_us, claimed)):
            if affected and jitter:
                offsets = _rng(p.seed, node, factor).integers(-jitter, jitter + 1, n)
                offsets[np.isin(nominal, list(knots))] = 0
                array += offsets
        claimed += true - nominal
        force, gyro, qs, qk, ns, nk = _geometry(trajectory, node, true.astype(np.float64) / 1e6, identity_axes)
        if affected:
            gyro[:, 2] += sign * (
                p.bias_rads + p.ramp_rads * np.maximum(true - 5_000_000, 0) / (motion.end_us - 5_000_000)
            )
            if p.heading_rate_rads:
                sensor = Rotation.from_quat(qs, scalar_first=True)
                if p.heading_path == "sensor":
                    gyro += sensor.inv().apply(np.tile([0, 0, sign * p.heading_rate_rads], (n, 1)))
                else:
                    yaw = Rotation.from_euler(
                        "Z", (sign * p.heading_rate_rads * (true - 5_000_000) / 1e6)[:, None]
                    )
                    qk = (yaw * Rotation.from_quat(qk, scalar_first=True)).as_quat(scalar_first=True)
            if p.accel_sigma:
                force += _rng(p.seed, node, 11).normal(0, p.accel_sigma, (n, 3))
            if p.gyro_sigma:
                gyro += _rng(p.seed, node, 12).normal(0, p.gyro_sigma, (n, 3))
        if p.calibration:
            force = force / [1.02, 0.98, 1.01] + [0.02, -0.01, 0.03]
            gyro = gyro + [0.001, -0.002, 0.003]
        scale = 1 + p.clock_ppm / 1e6 if node == "B" else 1.0
        offset = 250000.0 if node == "B" and (p.clock_enabled or p.clock_ppm) else 0.0
        unrounded = scale * claimed + offset
        device = np.rint(unrounded).astype(np.int64)
        keep = np.ones(n, dtype=np.bool_)
        sequence = np.arange(n, dtype=np.int64)
        if affected and p.loss != "none":
            peak_us = 5_000_000 + motion.cycles[0].rise_us
            peak_index = peak_us // (1_000_000 // sample_hz)
            packet = sequence // 4
            deleted = {
                "sample-one": sequence == peak_index,
                "sample-per": (sequence > 500) & (sequence % 100 == 0),
                "sample-burst": (nominal >= peak_us - 20000) & (nominal <= peak_us + 40000),
                "packet-one": packet == peak_index // 4,
                "packet-per": (packet > 125) & (packet % 25 == 0),
                "packet-burst": (packet >= peak_index // 4) & (packet <= peak_index // 4 + 1),
            }[p.loss]
            keep &= ~deleted
        qn = (Rotation.from_quat(qk, scalar_first=True) * Rotation.from_matrix(nk).inv()).as_quat(scalar_first=True)
        nodes[node] = NodeSource(
            sequence[keep],
            nominal[keep],
            true[keep],
            claimed[keep],
            device[keep],
            force[keep],
            gyro[keep],
            qs[keep],
            qk[keep],
            qn[keep],
            ns,
            nk,
            keep,
            1 / scale,
            -offset / scale,
            (device - unrounded)[keep],
        )
        for value in vars(nodes[node]).values():
            if isinstance(value, np.ndarray):
                value.setflags(write=False)
    return DualSource(trajectory, perturbation, nodes, sample_hz)


def quantize(values: FloatArray, lsb: float) -> IntArray:
    """Ties to even; reject range exceedance rather than clip."""
    if not np.isfinite(lsb) or lsb <= 0 or not bool(np.isfinite(values).all()):
        raise ValueError("quantization requires finite input and positive LSB")
    counts = np.rint(values / lsb)
    if bool(((counts < -32768) | (counts > 32767)).any()):
        raise ValueError("quantized source exceeds int16 range")
    return counts.astype(np.int64)


def packets(row: NodeSource, node: str) -> tuple[SamplePacket, ...]:
    """Frame original groups of four; retained packet/sample counters never change."""
    accel = quantize(row.force_mps2, ACCEL_LSB)
    gyro = quantize(row.rate_rads, GYRO_LSB)
    result = []
    for packet_index in np.unique(row.sequence // 4):
        indices = np.flatnonzero(row.sequence // 4 == packet_index)
        samples = tuple(
            Sample(
                int(row.sequence[i]),
                int(row.device_time_us[i]),
                SampleFlags.NONE,
                (int(accel[i, 0]), int(accel[i, 1]), int(accel[i, 2])),
                (int(gyro[i, 0]), int(gyro[i, 1]), int(gyro[i, 2])),
            )
            for i in indices
        )
        result.append(SamplePacket(NodeId[node], int(packet_index), 0, PacketFlags.NONE, samples))
    return tuple(result)
