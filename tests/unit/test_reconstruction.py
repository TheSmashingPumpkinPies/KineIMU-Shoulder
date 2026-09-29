"""Independent scalar, non-fixture-labelled tests of processed gap support."""

from math import cos, sin

import numpy as np
import pytest

from kineimu_shoulder.reconstruction import reconstruct_short_gaps


@pytest.mark.parametrize("times,knot", [
    ([0, 10000, 20000, 30000, 50000, 60000, 70000], 40000),
    ([0, 10000, 20000, 30000, 80000, 90000, 100000], 60000),
    ([0, 10700, 19100, 30500, 51200, 60300, 70000], 40123),
])
def test_transition_from_gravity_preserves_every_original_observation(times, knot):
    t = np.array(times, dtype=np.int64)
    angle = np.minimum(t, knot) / 1e6
    force = np.array([[-9.80665 * sin(a), 0, 9.80665 * cos(a)] for a in angle])
    rate = np.zeros_like(force)
    rate[t <= knot, 1] = 1
    r = reconstruct_short_gaps(t, force, rate, max_gap_s=.05)
    assert r.knots[0][:3] == (3, 4, knot)
    assert r.knots[0][3] < 1e-12
    np.testing.assert_array_equal(r.timestamp_us[r.observed_indices], t)
    np.testing.assert_array_equal(r.acceleration_mps2[r.observed_indices], force)
    np.testing.assert_array_equal(r.angular_rate_rads[r.observed_indices], rate)
    inserted = int(np.flatnonzero(r.timestamp_us == knot)[0])
    np.testing.assert_allclose(r.acceleration_mps2[inserted],
                               [-9.80665 * sin(knot / 1e6), 0, 9.80665 * cos(knot / 1e6)], atol=1e-12)
    assert r.angular_rate_rads[inserted].tolist() == [0, 1, 0]


def test_gravity_cannot_reconstruct_yaw_transition():
    t = np.array([0, 10000, 20000, 30000, 50000, 60000], dtype=np.int64)
    force = np.tile([0., 0., 9.80665], (len(t), 1))
    rate = np.zeros_like(force)
    rate[t <= 40000, 2] = 1
    r = reconstruct_short_gaps(t, force, rate, max_gap_s=.05)
    assert not r.knots
    np.testing.assert_array_equal(r.timestamp_us, t)


@pytest.mark.parametrize("mutation", ["long-gap", "linear-acceleration", "unconfirmed-branch", "nonfinite"])
def test_unsupported_input_is_not_rescued(mutation):
    t = np.array([0, 10000, 20000, 30000, 50000, 60000], dtype=np.int64)
    angle = np.minimum(t, 40000) / 1e6
    force = np.array([[-9.80665 * sin(a), 0, 9.80665 * cos(a)] for a in angle])
    rate = np.zeros_like(force)
    rate[t <= 40000, 1] = 1
    if mutation == "long-gap":
        t[4:] += 40000
    elif mutation == "linear-acceleration":
        force *= 2
    elif mutation == "unconfirmed-branch":
        rate[2, 1] = .5
    else:
        force[4, 0] = np.nan
    r = reconstruct_short_gaps(t, force, rate, max_gap_s=.05)
    assert not r.knots
    np.testing.assert_array_equal(r.timestamp_us, t)
    np.testing.assert_array_equal(r.acceleration_mps2, force)
