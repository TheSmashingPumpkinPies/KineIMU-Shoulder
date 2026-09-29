# M1 synthetic clock-mapping TDD experiment

This deterministic validation fixture exercises the M1 mapping/report path
before physical collection. It uses six common events: E01/E03/E05 are fit
events and E02/E04/E06 are held-out events, with coverage at beginning, middle
and end. The synthetic device times are integer-rounded values generated from
the analytical inverse

```text
t_device = (t_common - b) / a
```

with predeclared coefficients:

| Node | `a` | `b` (µs) | relative drift |
|---|---:|---:|---:|
| A | 1.000020 | 1250 | +20 ppm |
| B | 0.999970 | -750 | -30 ppm |

The event plan is not physical acquisition data. Its raw hashes are synthetic
provenance identifiers and must not be verified with `--verify-raw`.

## Reproduce

From the repository root:

```text
python -m validation.m1_clock_mapping \
  --event-plan experiments/m1_clock_mapping_synthetic_20260915/event_plan.json \
  --output experiments/m1_clock_mapping_synthetic_20260915/result.json
```

The report preserves the event IDs, fit/held-out split, localization method,
resolution, uncertainty, synthetic raw hashes, fit windows, coefficients,
offset/drift, residual quantiles and version. The raw-data policy is explicit:
resampling is `none` and raw data is unchanged.

This is a TDD/analytical verification artifact, not M1 physical timing
acceptance evidence. The rigid-fixture physical pilot is specified in
[`protocols/M1_CLOCK_MAPPING_FIXTURE.md`](../../protocols/M1_CLOCK_MAPPING_FIXTURE.md).
