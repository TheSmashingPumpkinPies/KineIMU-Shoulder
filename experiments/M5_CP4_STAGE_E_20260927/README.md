# CP4 stage E formal replay evidence

The 2026-09-27 maintainer continuation authorizes the two independent complete
B/C/segmented-D collections and separate CP4 pair audit. See
[entry and semantics](../../docs/M5_FORMAL_REPLAY.md).

Source/check preparation is in progress. Formal roots are frozen as
`experiments/M5_CP4_FORMAL_20260927/run1` and `run2` and must be absent before
launch. CP4 remains OPEN until both execute and independent audit passes.
Checks, execution commands/exits/PIDs, exact source ZIP, all raw/product hashes
and six numerical audits will be retained here. Old failed D evidence is immutable.

Test-first evidence: new collection guards failed9 before implementation;
independent audit guards failed4 before its implementation. Initial green had
an incorrect existing input constant import, fixed before verification.
The initial sandbox pytest attempt failed on Windows temporary-directory
permissions; normal-permission runs capture actual exits.
