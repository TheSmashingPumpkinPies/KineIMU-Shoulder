# ADR-015 — Audit and sanitize public research-data copies

Status: Accepted by explicit maintainer instruction on 2026-09-29.

## Authority

The maintainer approves in principle the additional 703 data/companion files for
KineIMU Shoulder's public repository, conditional on a complete pre-publication
audit. Unreviewed absolute machine paths and unique device identifiers are not
approved for publication. Once audited and verified, passing copies may be uploaded
to the maintainer-created KineIMU-Shoulder repository. No new upload confirmation is
required for those passing copies. Tag/Release/PyPI remain outside this task.

## Required treatment

Keep the previously approved 25 CC0 sample members and their authorization scope.
Review every additional member for paths/usernames, unique device identifiers,
credentials, personal data and third-party copyright/redistribution terms. Check
all other selected public content and nested containers for the same disclosures.
Use repository-relative paths or generic placeholders; use consistent anonymous
device identities while retaining model, firmware, sample configuration and
experimental conditions. Retain failed attempts and their actual dispositions.

Retain untouched originals locally. Produce separate public copies and a private
original/public member and SHA-256 mapping. Neither original files nor that mapping
is included in the public Git history. The public report contains safe aggregate
counts/reasons and public-only integrity records, not private original identities.

Substantive experimental results, counters, timestamps, measurements, failures and
validation conclusions must not change. Metadata privacy changes and resulting
public-copy digest updates must be explicit; preserve private original hashes and
acceptance identities. Hash anchors in public-copy checks may bind reviewed public
copies but must not replace or weaken numerical/experimental acceptance assertions.

Apply CC0 only to original data with reviewed provenance/ownership/publication
authority. Preserve original code, firmware, notices and dependencies under their
applicable licenses. Exclude unresolved material with a documented reason rather
than asserting unverified ownership. Re-run tests, independent numerical audits,
benchmark reconstruction/recomputation, package checks and fresh-clone reproduction
on the final public copies. Report Windows and Linux CI separately.

Start clean public Git history after audit. Do not upload preparation commits,
unsanitized records, local development caches, private refs or mapping files.
The private source-development repository and original evidence remain unchanged
apart from the authorization/audit/state documents for this task.
