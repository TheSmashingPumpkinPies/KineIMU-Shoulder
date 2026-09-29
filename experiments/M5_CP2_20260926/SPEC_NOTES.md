# CP2 source interpretation notes

The frozen F4/VAR prose says cycle starts are 5, 9.5 and 15 seconds. Its
parameter table and continuous cycle equations instead give the third start
as `9.5 + 1.5 + 1 + 1 + 1 = 14` seconds. The accepted CP1 source and retained
independent nominal annotations already use 14 seconds; CP2 uses those
unchanged parameters and annotations. The session still ends at 21 seconds,
including an additional quiet tail. This is a prose/parameter inconsistency,
not a discovered change to raw observations or metric truth during CP2.

No frozen file, budget, input or label is edited in this checkpoint. CP2
numerical conclusions refer explicitly to the retained CP1 parameter-defined
source, not to the inconsistent prose timestamp. Any later normative prose
correction must preserve the original freeze/hash, record a reviewed version
and declare its rerun scope under the M5 contract. The current formal run
manifests retain the exact frozen truth hash and source lock.

CP2 also declares synthetic UTC ordering metadata for summary comparisons;
it uses September 26 for baseline sessions and September 27 for F90-NEXT.
These are declared chronological labels, not measured acquisition UTC or
an absolute-time accuracy claim. Device/common-time errors and all numeric
gates use the independently known integer-microsecond motion timeline.

M4 receives stationary initialization rows as arming context. Error/coverage
denominators exclude [0,5] seconds, and PARTIAL preserves its explicit crop.
The original M4 empty active-time sum is valid zero, while empty ROM/SD/CV/
cadence retain their exact availability reasons. These distinctions are
recorded in [the runner documentation](../../docs/M5_BASELINE.md).
