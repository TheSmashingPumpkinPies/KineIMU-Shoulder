# README visualization

`synthetic-motion.png` shows **synthetic** humerothoracic elevation from the existing
M6 stored-Q sample. It is generated from actual replay products, not nominal
90-degree trajectories or independent reference annotations.

From the repository root, using the project's documented Python and uv versions:

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-readme
uv run --frozen --with matplotlib==3.11.1 python scripts/plot_readme_demo.py --demo demo-output-readme
```

Use a new demo output directory each time. Matplotlib is only needed for figure
generation; normal demo execution and viewing the README need no plotting package.
The plotting script also accepts `--output` for a separate figure directory.

For each of F90, AL90, AR90 and T-MIX, the plot reads `processed.json.gz` fields
`relative.common_time_us`, `elevation`, `elevation_valid` and
`evaluation_window_us`. It converts microseconds to seconds and radians to degrees,
clips the view to the analysis window, and leaves invalid samples as gaps.
There is no smoothing, resampling or generated replacement signal. Repetition
counts come from `derived.json.gz` → `summary.valid_count`.

The script requires `demo_passed=true`, unchanged input hashes and matching hashes
for each plotted product. [Figure provenance](synthetic-motion.provenance.json)
records the analysis source revision, input and product SHA-256 identities, analysis
runtime and plotting versions. A rerun may have different compressed-product hashes
or raster bytes with different metadata/runtime; these are not accuracy measures.

All four trajectories use constructed calibration, initial heading, alignment and
clock assumptions, with `anatomical_eligible=false`. The figure is not evidence of
human, glenohumeral, scapular or clinical accuracy. Original sample licensing and
provenance remain in [the sample directory](../../datasets/samples/m6_synthetic/README.md).
The system diagram in the root README is maintained as GitHub-rendered Mermaid.
