# Candidate verification attempts

The first patch submission was rejected before any edits because it specified
both deletion and addition of LICENSE in one patch. Resubmitted as an update.
A later review-document patch had one mismatched expected line and made no
changes; the two current decision/packaging documents were then rewritten.

The first Ruff check, ruff-01, found one E501 line: the expanded archive
metadata field list was 124 characters against the existing 120-character
limit. Split that list across lines. The original exit/log remain retained;
ruff-02 is a new check, not a replacement log. No numerical or production
behavior changed. Actual command records are authoritative.

Source preparation commit c70bbab4 emitted Git text-conversion warnings for new
Windows command records and runtime-summary.log. Their disk bytes and recorded
hashes were unchanged, but Git would normalize their CRLF. Added narrowly scoped
archival attributes for this new evidence directory and restaged only its own
records from original disk bytes. This preserves command log hashes and the
declared runtime copy in Git. No prior evidence or production file was converted.

The first complete licensed-candidate regression (full-01) returned 877 passed,
1 failed, 0 skipped. The legacy BLE experiment gate emitted completion after
110 ms for a required 120 ms firmware-CDC-connected settle window.
A deterministic early-timer-wakeup regression (settle-red-01) reproduced the
missing post-sleep deadline check: 1,110,000,000 instead of 1,120,000,000 ns.
The live experiment runner now rechecks the monotonic deadline together with
connection-generation validity before completing; settle-green-01 passed all
19 timing contracts. No tolerance was relaxed.
The installed CPython 3.12.14 asyncio/base_events.py _run_once advances scheduled
handles into ready through self.time() + self._clock_resolution. This supports
the early-wakeup mechanism; the exact original OS scheduling trace was not
captured. The deterministic regression establishes the gate defect directly.
This is an experiment-only host wait guard, outside the distribution. Firmware,
USB acquisition, physical raw evidence, archived BLE dispositions and all
production/numerical implementations remain unchanged; no hardware action ran.

Candidate01 artifacts and source-snapshot.json remain retained unchanged.
Candidate02 additionally corrects current verification navigation in README/
technical report and removes an obsolete pending-license paragraph from
THIRD_PARTY_COMPATIBILITY. A new source-snapshot-final.json records its inputs.

Final navigation review found one remaining unqualified pending-permission
sentence in docs/M6_DEMO.md. It now states the approved CC0 annex governs
selected originals while historical labels remain unchanged. This repository
document is not in wheel/sdist: candidate02 packaged bytes were unaffected.
source-snapshot-final.json and committed-source-final.json retain the earlier
source checkpoint exactly; the final delivery snapshot binds the current demo
document and closing verification records separately. docs-final-04 checks the
corrected current documentation. No test or processing input changed.
