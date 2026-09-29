# Retained preview attempts

- `build-01` successfully built internal artifacts in `dist/m6-review-01`.
  Archive check `archives-red-01` failed: wheel notice snapshot absent due to
  Hatchling 1.27.0 nonrecursive `glob()`. That build also predates the later
  two upstream-reference texts. Both the original files and failed report remain.
- Explicit wheel shared-data inclusion replaced the unsupported recursive
  license-file assumption. `build-02` / `archives-green-02` passed. Versions,
  algorithms, source package and uv.lock remained unchanged.
- Initial `ruff-01` / `mypy-01` could not initialize the existing protected uv
  cache (exit 2). No checker ran. Ordinary-permission `ruff-02` / `mypy-02`
  were separate actual checks and passed; original failures retained.
- First independent install run completed all eight commands successfully;
  original wheel/sdist command output and isolated API JSON remain in their
  `.log` files. A helper-file naming collision caused the outer generic record
  `independent-installs.json` to overwrite the child's same-named detailed
  record. That lost detail is not reconstructed or treated as a complete audit.
  The helper now uses a distinct `installation-audit-<label>.json` and unique
  per-command logs. A new absent external root and `attempt02` provide the
  authoritative complete install command/time/exit/hash record.
- `build-03` includes final CFF-schema attribution and release byte attributes;
  its archive check and separate `attempt03` installs are the final preview
  acceptance evidence. `attempt02` success remains retained, not relabeled.
- `ruff-final` caught one 121-character line in the installation verifier;
  line wrapping corrected it without changing executed API behavior. Its failure
  is retained; the final checker record uses a new name.
- First staged whitespace check reported original trailing spaces in upstream
  license texts. Those texts were not edited. Git now treats only the copied
  upstream `.txt` notice payloads as archival binary bytes; the original-text
  SHA-256 audits remain the identity gate and project prose/code still receive
  normal whitespace checks. The first freeze map is retained as
  `source-snapshot-attempt01.json`; the replacement freeze binds the scoped
  attribute change and this explanation without overwriting the old record.

No failed/first root is overwritten or removed. New attempts have new filenames
and environment roots. CP4 remains OPEN pending final release decisions.
