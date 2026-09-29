# Post-freeze staging checks

The first staged-byte probe stopped before completion because the retained build
directories contain uv-generated `.gitignore` files (`*`), copied with the
original artifact outputs. Those patterns hid the retained binaries and the
ignore-file copies from ordinary directory staging. No artifact bytes were
missing or changed on disk. The nine known files (six wheel/sdist binaries plus
three original ignore-file copies) were explicitly force-staged in the scoped
artifact directory, then the complete frozen-byte comparison was rerun.

This note and later check/proof records are outside the frozen delivery map.
They do not revise its contents or retroactively change any failed attempt.

The next complete byte probe found one existing source EOL relationship:
`kineimu_shoulder/summary.py` on disk uses CRLF while the unchanged HEAD/index
uses LF. No module edit or package-behavior change occurred. Its actual runtime
bytes (16,688 bytes) are retained in `runtime-summary.log`; the final freeze
records both Git and runtime hashes. The proof allows exactly CRLF→LF replacement
for this single named original file and compares the entire result byte-for-byte;
all other frozen members require exact Git/disk equality. Source and artifact
bytes are never normalized in place. This is a source identity record, not a
numerical transformation or an expansion of historical M5/CP3 allowances.
Earlier failed/withdrawn freeze maps remain as attempts; only the final
`source-snapshot.json` is the current proof input.
