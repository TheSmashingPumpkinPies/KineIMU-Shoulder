# M5 remote synchronization preflight — 2026-09-28

## Current maintainer decision

After reviewing the oversized evidence, the maintainer explicitly deferred
remote synchronization and evidence-storage handling until M6 and overall
project closeout. The pre-M6 synchronization prerequisite is superseded.
M6.0 may proceed; the migration/archive options below remain proposals for
final publication, not authorization to rewrite history or remove evidence.
The preflight JSON records the original observation and is retained unchanged.

Maintainer requested synchronization to the existing GitHub remote before M6
implementation. Entry main: d95ec7fb59e569994e132c21b1b28ad1ac800147.
Fetched origin/main: 02901e80dfd02603ffadb55772600748f9cb1bb4.
The entry branch is 53 commits ahead, zero behind; normal-permission tracked
status is clean. M0–M5 acceptance and the M6 planning document are retained.
M6 CP0–CP5 remain OPEN; this segment performs no M6 implementation.

## Blocking objects

The read-only object scan found four distinct ordinary Git blobs above the
GitHub 100 MiB limit. See M5_REMOTE_SYNC_PREFLIGHT_20260928.json for exact
object IDs, byte sizes and all current HEAD paths. Several objects occur at
multiple retained paths. The largest object is 158320276 bytes. Newly reachable
blob content totals 4326008278 uncompressed bytes across 7186 distinct blobs.
These figures describe repository storage, not algorithm performance.

GitHub documents its limit at
https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github.
Adding LFS attributes in a new tip commit cannot remove ordinary oversized
blobs already reachable through earlier commits. No push has been attempted;
no remote ref, original commit, experiment file or evidence map was changed.

## Concrete decision and execution gates

History migration requires explicit maintainer authorization because original
M5 provenance binds exact commits. Git LFS 3.7.1 is installed. Before any
migration, create and verify a recoverable Git bundle retaining the original
history and refs; keep the original checkout/evidence untouched while preparing
an isolated publication checkout. Do not force-update published history.

If authorized, migrate only unpublished history needed by main, record the
original-to-publication commit map and every moved blob's SHA-256/size, and
verify byte identity after LFS retrieval. Original numerical/source/evidence
locks must remain resolvable from the preserved history. Do not rewrite
immutable M5 evidence reports merely to substitute publication SHAs.
Document how a remote user retrieves and verifies original locks before
claiming reproducible publication. Verify the resulting branch remains a
descendant of the fetched remote main, and upload required LFS content before
the final normal fast-forward push. The migration is not yet authorized or
implemented; it may expose further storage/provenance decisions.

If the maintainer requires every original commit SHA to remain the mainline
identity, ordinary GitHub push cannot meet that requirement. Prepare a separately
approved archive destination or full-history bundle distribution, and label
archive backup separately from local/remote main equality.

## Fresh verification and next action

Documentation consistency: 1236 Markdown files, 39 archive hashes, zero errors,
exit 0 at entry. Whitespace check exit 0. Agent context command exit 0; its
large output is preserved in local scratch .tmp-m5-remote-sync-20260928.
No Python/firmware change, numerical rerun, pytest/lint/type/build acceptance
or hardware action is claimed. Repeat docs/whitespace checks after this state
update. The original pending storage question was superseded by the deferral
above. Next: M6.0 contract/checklist/benchmark draft freeze; reconsider storage
and synchronization together at final M6/project closeout.
