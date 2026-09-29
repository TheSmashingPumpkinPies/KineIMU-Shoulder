"""Read-only failed-attempt diagnostic; never supplies modified data to AHRS."""
import argparse
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np

from kineimu_shoulder.calibration import CalibrationArtifact, apply_calibration
from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, decode_sample_packet

root = Path(__file__).resolve().parents[2]
external = Path('<external-data>/kineimu_m1_usb_30min_20260925_01')
evidence = root/'experiments/M5_CP4_STAGE_D_20260927'
output = root/'experiments/M5_CP4_STAGE_D_DUAL_USB_20260927'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert not args.output.exists(), 'diagnostic output must be fresh'
assert not args.output.resolve().is_relative_to(external.resolve()), 'diagnostic cannot write in raw acquisition root'
source = external/'raw/node-b.kimu'
raw = source.read_bytes()
digest = sha256(raw).hexdigest()
assert digest == '0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68'
records = list(iter_capture_records(BytesIO(raw)))
packets = [decode_sample_packet(r.payload) for r in records]
samples = [s for p in packets for s in p.samples]
assert len(records) == 47856 and len(samples) == 191424
assert all(p.node_id == NodeId.B and p.clock_epoch == 0 for p in packets)
acc = np.asarray([s.accel_raw for s in samples]) * (0.122e-3*9.80665)
rate = np.deg2rad(np.asarray([s.gyro_raw for s in samples])*17.5e-3)
result = json.loads((output/'cases/M1-B/result.json').read_bytes())
epoch = result['epochs'][0]
assert epoch['device_time_us'] == [s.device_time_us for s in samples]
assert epoch['sample_sequences'] == [s.sequence for s in samples]
assert epoch['sample_flags'] == [int(s.flags) for s in samples]
assert epoch['packet_sequences'] == [p.packet_sequence for p in packets]
assert epoch['packet_flags'] == [int(p.flags) for p in packets]
assert epoch['host_monotonic_ns'] == [r.host_monotonic_ns for r in records]
assert np.allclose(epoch['sensor_acceleration_mps2'], acc, rtol=0, atol=1e-14)
assert np.allclose(epoch['sensor_angular_rate_rads'], rate, rtol=0, atol=1e-14)
artifact = CalibrationArtifact.from_json(json.dumps(result['calibration']))
try:
    apply_calibration(acc, rate, artifact=artifact, node_id=NodeId.B, sensor_id='LSM6DS3TR-C',
                      config=artifact.config, sample_flags=tuple(s.flags for s in samples))
except ValueError as exc:
    actual_error = str(exc)
else:
    raise AssertionError('original B unexpectedly calibrated')
assert actual_error == 'clipped samples cannot be used for calibration'
indices = [i for i,s in enumerate(samples) if s.flags]
exceeds = np.flatnonzero(np.any(abs(rate) > np.deg2rad(500)*1.001, axis=1)).tolist()
rows = []
for i in sorted(set(indices+exceeds)):
    s = samples[i]
    rows.append(dict(original_index=i, sample_sequence=s.sequence, device_time_us=s.device_time_us,
        elapsed_from_first_sample_s=(s.device_time_us-samples[0].device_time_us)/1e6,
        sample_flags=int(s.flags), packet_sequence=packets[i//4].packet_sequence,
        accel_raw=list(s.accel_raw), gyro_raw=list(s.gyro_raw),
        acceleration_mps2=acc[i].tolist(), angular_rate_rads=rate[i].tolist(),
        angular_rate_dps=np.rad2deg(rate[i]).tolist(), clipped_flag=i in indices,
        exceeds_existing_configured_gyro_gate=i in exceeds))
after = sha256(source.read_bytes()).hexdigest()
assert digest == after
record = dict(disposition='FAILED; D complete AHRS requirement unsatisfied',
    source_lock='6a305eed744caa89276ea3d0961afc468ab398e4',
    original_failed_root=output.relative_to(root).as_posix(), source_sha256_before=digest, source_sha256_after=after,
    complete_B_original_packets_checked=len(packets), complete_B_original_rows_checked=len(samples),
    clipped_flagged_row_count=len(indices), gyro_configured_gate_exceedance_row_count=len(exceeds),
    acceleration_configured_gate_exceedance_row_count=int(np.any(abs(acc)>4*9.80665*1.001,axis=1).sum()),
    reproduced_original_calibration_error=actual_error, gyro_configured_range_dps=500,
    existing_range_gate_tolerance_factor=1.001, gyro_max_abs_dps=float(abs(np.rad2deg(rate)).max()),
    flagged_or_range_exceeding_original_rows=rows,
    untouched_facts=['Original flags/counters/times/SI preserved in failed product.',
                     'No flags removed, no rows filtered or raw overwritten.',
                     'No range gate relaxed, config changed or calibration bypassed.',
                     'B AHRS and dual downstream remain NOT RUN; no D/CP4 acceptance.',
                     'M1 acquisition stability pass remains distinct from calibration usability.',
                     'This does not establish a firmware/acquisition defect or authorize hardware reopening.'])
with args.output.open('xb') as stream:
    stream.write((json.dumps(record, sort_keys=True, indent=2, allow_nan=False)+'\n').encode())
print(json.dumps({k:v for k,v in record.items() if k != 'flagged_or_range_exceeding_original_rows'},indent=2))
print('original rows', rows)
