"""CP1 tool gates; expected values derive from M5 O/F/T/P fixtures, not M3/M4."""

import importlib.util
from math import pi

import numpy as np
import pytest
from scipy.spatial.transform import Rotation


def test_cp1_source_exists():
    assert importlib.util.find_spec("kineimu_shoulder.validation.source") is not None


def api():
    from kineimu_shoulder.validation import oracle, source

    return source, oracle


@pytest.mark.parametrize("trajectory,axis,sign", [("F90", 2, -1), ("AL90", 1, 1), ("AR90", 1, -1)])
def test_o1_o4_force_and_handedness(trajectory, axis, sign):
    source, _ = api()
    data = source.generate(trajectory)
    np.testing.assert_allclose(data.nodes["A"].force_mps2[0], [-9.80665, 0, 0], atol=1e-12)
    np.testing.assert_allclose(data.nodes["B"].force_mps2[0], [9.80665, 0, 0], atol=1e-12)
    expected = np.zeros(3)
    expected[axis] = sign * pi / 3
    np.testing.assert_allclose(data.nodes["B"].rate_rads[600], expected, atol=1e-12)
    assert np.array_equal(data.nodes["A"].sequence, np.arange(2151))


@pytest.mark.parametrize(
    "trajectory",
    ["QUIET", "F90", "AL90", "AR90", "VAR", "NOHOLD", "WRONG", "PARTIAL", "T-EXT", "T-MIX", "F90L", "F90-NEXT"],
)
def test_o5_t1_independent_matrix_reference(trajectory):
    source, oracle = api()
    data = source.generate(trajectory)
    for node in ("A", "B"):
        for index in (0, 537, 623, 813, len(data.nodes[node].sequence) - 1):
            row = data.nodes[node]
            reference = oracle.sensor_reference(trajectory, node, row.true_time_us[index] / 1e6)
            np.testing.assert_allclose(row.force_mps2[index], reference[0], atol=1e-11)
            np.testing.assert_allclose(row.rate_rads[index], reference[1], atol=1e-6)
            matrix = Rotation.from_quat(row.q_ws[index], scalar_first=True).as_matrix()
            np.testing.assert_allclose(matrix, reference[2], atol=1e-12)


def test_f1_f4_labels_and_t0_proxy():
    _, oracle = api()
    labels = oracle.labels("F90")
    rep = labels[0]
    assert (rep["start_us"], rep["peak_us"], rep["end_us"]) == (5340000, 6500000, 9280000)
    assert rep["confirm_start_us"] == 5540000
    assert rep["confirm_end_us"] == 9480000
    assert rep["rom_rad"] == pytest.approx(80.1 * pi / 180, abs=1e-12)
    assert rep["duration_s"] == 3.94
    assert rep["hold_s"] == 1
    var = oracle.labels("VAR")
    assert [r["end_us"] - r["physical_start_us"] for r in var] == [3220000, 3380000, 4840000]
    assert [r["rom_rad"] * 180 / pi for r in var] == pytest.approx([60.2, 70.4, 80.4])
    proxy = oracle.proxy("T-EXT", 5340000, [5340000, 6500000, 9280000])
    np.testing.assert_allclose(proxy[:, 0] * 180 / pi, [0, 7.733333333333333, -1.166666666666667], atol=1e-12)
    assert sum(r["complete"] for r in oracle.labels("F90L")) == 54
    assert sum(r["eligible"] for r in oracle.labels("PARTIAL")) == 1


def test_o6_zero_perturbation_calibration_and_left_knots():
    source, _ = api()
    clean = source.generate("F90")
    zero = source.generate("F90", source.Perturbation())
    applied = source.generate("F90", source.Perturbation(calibration=True))
    for node in ("A", "B"):
        assert np.array_equal(clean.nodes[node].force_mps2, zero.nodes[node].force_mps2)
        recovered = (applied.nodes[node].force_mps2 - [0.02, -0.01, 0.03]) * [1.02, 0.98, 1.01]
        np.testing.assert_allclose(recovered, clean.nodes[node].force_mps2, atol=1e-12)
        np.testing.assert_allclose(
            applied.nodes[node].rate_rads - [0.001, -0.002, 0.003], clean.nodes[node].rate_rads, atol=1e-12
        )
    assert clean.nodes["B"].rate_rads[650, 2] == pytest.approx(-pi / 3)
    assert clean.nodes["B"].rate_rads[750, 2] == 0
    assert clean.nodes["B"].rate_rads[950, 2] == pytest.approx(pi / 4)


def test_p3_p4_p7_times_and_pcg_streams():
    source, oracle = api()
    p = source.Perturbation(seed=1103, target="SAME", accel_sigma=0.02, gyro_sigma=0.005, sample_jitter_us=1000)
    data = source.generate("T-MIX", p)
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([1103, 2, 11])))
    noise = rng.normal(0, 0.02, (2151, 3))
    for i in (537, 623, 813):
        row = data.nodes["B"]
        ref = oracle.sensor_reference("T-MIX", "B", row.true_time_us[i] / 1e6)
        np.testing.assert_allclose(row.force_mps2[i] - noise[i], ref[0], atol=1e-11)
    timestamp = source.generate("F90", source.Perturbation(timestamp_jitter_us=1000, target="B", seed=1103))
    assert np.array_equal(timestamp.nodes["B"].true_time_us, timestamp.nodes["B"].nominal_time_us)
    assert not np.array_equal(timestamp.nodes["B"].device_time_us, timestamp.nodes["B"].true_time_us)
    clock = source.generate("F90", source.Perturbation(clock_ppm=500, target="B"))
    row = clock.nodes["B"]
    recovered = row.device_time_us / 1.0005 - 250000 / 1.0005
    assert np.max(np.abs(recovered - row.true_time_us)) <= 1


def test_p5_p6_loss_does_not_renumber():
    source, _ = api()
    for loss, missing in (
        ("sample-one", {650}),
        ("sample-burst", set(range(648, 655))),
        ("packet-one", set(range(648, 652))),
        ("packet-burst", set(range(648, 656))),
    ):
        data = source.generate("F90", source.Perturbation(loss=loss, target="B"))
        assert set(range(2151)) - set(data.nodes["B"].sequence) == missing
        assert len(data.nodes["A"].sequence) == 2151
    packets = source.packets(source.generate("F90", source.Perturbation(loss="packet-one", target="B")).nodes["B"], "B")
    assert 162 not in [p.packet_sequence for p in packets]
    assert packets[-1].packet_sequence == 537
    assert len(packets[-1].samples) == 3


def test_o7_quantization_round_even_and_bounds():
    source, _ = api()
    assert source.quantize(np.array([0.5, 1.5, 2.5, -0.5, -1.5]), 1).tolist() == [0, 2, 2, 0, -2]
    with pytest.raises(ValueError):
        source.quantize(np.array([32768.0]), 1)
    row = source.generate("T-MIX").nodes["B"]
    packets = source.packets(row, "B")
    raw = np.array([s.accel_raw for p in packets for s in p.samples])
    assert np.max(np.abs(raw * (0.122e-3 * 9.80665) - row.force_mps2)) <= 0.00059820565 + 1e-14
    assert [s.sequence for p in packets for s in p.samples] == list(range(2151))


def test_t1_mixed_gyro_integration_converges():
    source, _ = api()
    errors = []
    for hz in (100, 200):
        row = source.generate("T-MIX", sample_hz=hz).nodes["B"]
        rotation = Rotation.from_quat(row.q_ws[0], scalar_first=True)
        maximum = 0
        for i in range(1, len(row.sequence)):
            dt = (row.true_time_us[i] - row.true_time_us[i - 1]) / 1e6
            rotation = rotation * Rotation.from_rotvec(row.rate_rads[i] * dt)
            reference = Rotation.from_quat(row.q_ws[i], scalar_first=True)
            maximum = max(maximum, (rotation.inv() * reference).magnitude())
        errors.append(maximum)
    assert errors[0] <= pi / 450
    assert errors[1] / errors[0] <= 0.75


def test_nominal_labels_remain_separate_from_lost_observation_grid():
    source, oracle = api()
    data = source.generate("F90", source.Perturbation(loss="sample-one", target="B"))
    observed = oracle.observation_labels("F90", data.nodes["B"].true_time_us.tolist())
    assert oracle.labels("F90")[0]["peak_us"] == 6500000
    assert observed[0]["peak_us"] == 6510000
    assert observed[0]["truth_id"] == "F90:rep-1"
    summary = oracle.summary("VAR")
    assert summary["rom_mean_rad"] == pytest.approx((60.2 + 70.4 + 80.4) / 3 * pi / 180)
    assert summary["rom_sd_rad"] == pytest.approx(np.std(np.array([60.2, 70.4, 80.4]) * pi / 180, ddof=1))
    assert oracle.summary("QUIET")["rom_mean_rad"] is None


def test_o0_identity_axes_stationary_and_readonly_source():
    source, _ = api()
    data = source.generate("QUIET", identity_axes=True)
    for row in data.nodes.values():
        np.testing.assert_allclose(row.force_mps2[0], [0, 0, 9.80665], atol=1e-12)
        np.testing.assert_allclose(row.q_ws[0], [1, 0, 0, 0], atol=1e-12)
        assert not row.force_mps2.flags.writeable


def test_p1_p2_p8_bias_ramp_and_world_vertical_injection():
    source, oracle = api()
    clean = source.generate("T-MIX")
    biased = source.generate("T-MIX", source.Perturbation(bias_rads=pi / 9000, ramp_rads=pi / 4500, target="DIFF"))
    yaw = source.generate("T-MIX", source.Perturbation(heading_rate_rads=pi / 9000, target="B"))
    for i in (0, 537, 1000, 2150):
        expected = pi / 9000 + pi / 4500 * max(i * 0.01 - 5, 0) / 16.5
        assert biased.nodes["A"].rate_rads[i, 2] - clean.nodes["A"].rate_rads[i, 2] == pytest.approx(expected)
        assert biased.nodes["B"].rate_rads[i, 2] - clean.nodes["B"].rate_rads[i, 2] == pytest.approx(-expected)
        matrix = oracle.sensor_reference("T-MIX", "B", i * 0.01)[2]
        np.testing.assert_allclose(
            yaw.nodes["B"].rate_rads[i] - clean.nodes["B"].rate_rads[i], matrix.T @ [0, 0, pi / 9000], atol=1e-12
        )


def test_t2_common_world_yaw_preserves_relative_motion():
    source, _ = api()
    clean = source.generate("T-MIX")
    changed = source.generate("T-MIX", source.Perturbation(heading_rate_rads=pi / 9000, heading_path="world"))
    for i in (0, 537, 623, 950, 2150):
        ra = Rotation.from_quat(clean.nodes["A"].q_wk[i], scalar_first=True)
        rb = Rotation.from_quat(clean.nodes["B"].q_wk[i], scalar_first=True)
        ca = Rotation.from_quat(changed.nodes["A"].q_wk[i], scalar_first=True)
        cb = Rotation.from_quat(changed.nodes["B"].q_wk[i], scalar_first=True)
        assert ((ra.inv() * rb).inv() * (ca.inv() * cb)).magnitude() < 1e-12
    # T2/P8 explicit h=rate*(t-5), including negative pre-evaluation yaw.
    assert Rotation.from_quat(changed.nodes["A"].q_wk[0], scalar_first=True).magnitude() == pytest.approx(5 * pi / 9000)
