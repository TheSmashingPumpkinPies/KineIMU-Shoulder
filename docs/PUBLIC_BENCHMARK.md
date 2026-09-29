# Reproduce retained benchmark evidence

The retained [protocol1.1 report](../benchmarks/demo/REPORT.md) is Windows evidence.
Its six-slot batch is `experiments/M6_CP3_20260928/batch01`, with original raw
counter deltas and a reviewed54-member source ZIP. Machine/device metadata is
anonymous; related public-copy log/source/output hashes bind the reviewed files.
Current public metadata/navigation differ from that measured source. Reconstruction
was independently executed: all54reviewed source hashes, unchanged37CP1 and28sample members,
six numerical audits and complete statistics PASS. It does not forge the old Git
HEAD or claim that today's source was the measured commit.

Run from this repository root with Python3.12.14/uv0.12.5. Pick a new clone:

```powershell
$history = Join-Path $env:TEMP ("kineimu-benchmark-" + [guid]::NewGuid())
git clone --no-hardlinks . $history
@'
from pathlib import Path
import hashlib, json, sys, zipfile
root = Path(sys.argv[1]).resolve()
batch = root / "experiments/M6_CP3_20260928/batch01"
source = json.loads((batch / "runtime-source-sha256.json").read_bytes())
with zipfile.ZipFile(batch / "runtime-source.zip") as archive:
    assert set(archive.namelist()) == set(source)
    for name, digest in source.items():
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        data = archive.read(name)
        assert hashlib.sha256(data).hexdigest() == digest
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
# The CC0 annex was approved after measurement. Retain its unchanged bytes outside
# the old input directory in this reconstruction only; the active clone stays intact.
annex = root / "datasets/samples/m6_synthetic/LICENSE.md"
(root / "CURRENT_SAMPLE_CC0_PERMISSION.md").write_bytes(annex.read_bytes())
annex.unlink()
expected = json.loads((batch / "inputs-before.json").read_bytes())
for group, directory in (("sample", "datasets/samples/m6_synthetic"),
                         ("original", "experiments/M5_CP1_20260926/run1")):
    folder = root / directory
    actual = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in folder.rglob("*") if p.is_file()}
    assert actual == expected[group]
'@ | uv run --frozen python - $history
Push-Location $history
try {
    uv sync --extra analysis --frozen
    uv run --frozen python benchmarks/demo/run_benchmark.py --recompute experiments/M6_CP3_20260928/batch01 --output "$history-recomputed.json"
} finally {
    Pop-Location
}
```

An output file already present is refused. The active
checkout is unchanged by this reconstruction. Public-copy maps bind reviewed bytes;
untouched originals and their correspondence remain private. Recomputed five timed values exclude warmup and match the
old summary exactly; machine/path metadata is anonymous; original timing/statistical values are unchanged.
Two optional physical replay tests and Linux execution are separate claims.

For a new performance batch at current source, follow
[the original new-batch procedure](../benchmarks/demo/REPRODUCE.md#run-a-new-batch).
The fixed preflight pair remains valid for unchanged scientific source. Formal
runs need clean tracked source, exact pinned versions, an unused external output
root and no concurrent tests or edits. If scientific source changes, collect and
independently audit a new reference pair before updating a protocol.
