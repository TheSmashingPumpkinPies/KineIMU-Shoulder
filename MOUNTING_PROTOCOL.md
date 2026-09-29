# Mounting Protocol — KineIMU Shoulder

Status: future human/wearable work under ADR-008. The frame/placement vocabulary may
inform synthetic and replay metadata, but physical wear validation is not a V1 gate.
This is a placement concept, not evidence of anatomical accuracy.

## Nodes

- A — Thorax: anterior sternum, preferably flat area below jugular notch.
  Thorax orientation, trunk reference and thorax compensation measurement.
- B — Upper Arm / Humerus: test-side lateral upper arm near mid-humerus,
  approximately between biceps and triceps. Upper-arm segment orientation.
- Together: humerothoracic movement; not isolated glenohumeral motion or scapular rotation.

## If future wearable acquisition is authorized

Document landmarks, offsets, test side, board revision, physical axis diagram, face orientation,
strap/adhesive orientation, clothing, enclosure/battery and total mounted mass.
Use reproducible fixtures limiting slippage and cable pull. Record soft-tissue motion and migration;
stop unstable trials. Do not switch mounting methods silently.
Record supporting placement literature before formal validation; literature-informed is not a
substitute for source appraisal or mounting tests.

No current milestone requires a battery, soldering, enclosure, retention prototype or
human wear trial. A later approved study must specify those items before collection.

## Per-session record and alignment

Pseudonymous node IDs/A-B roles, protocol version, operator, side, calibration IDs, neutral pose,
functional maneuver where needed, remount flag and slippage notes. Follow data governance for images.
M2 defines both sensor-to-segment transforms and uncertainty.
Neutral static pose constrains gravity, not complete 3D anatomical heading.

## Future don/doff repeatability

Remove both sensors, remount using this protocol, repeat alignment and prescribed exercise.
Compare within-mount and between-mount ROM, peaks and thorax excursions.
Retain operator/day/side/alignment changes; repetitions are not independent subjects.
A separately approved human-validation plan must set justified study size,
endpoint-specific references, governance and ethics requirements.
