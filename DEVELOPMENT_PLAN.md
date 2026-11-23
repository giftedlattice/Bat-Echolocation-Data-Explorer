# Development plan

This plan is intentionally non-invasive. No task below authorizes code or schema changes by itself; approval is required before implementation.

## Phase 0 — Stabilize and baseline

- [ ] Freeze the current database as a named compatibility fixture.
  - Acceptance: a checksum, row counts, schema inventory, and read-only handling instructions are recorded without exposing sensitive data.
- [ ] Decide and document supported Python versions and platforms.
  - Acceptance: a clean environment can install the declared dependencies and import every required module.
- [ ] Add a versioned schema baseline generated from the approved current schema.
  - Acceptance: a fresh temporary database can be created without copying production data, and its metadata matches the approved baseline.
- [ ] Add a schema compatibility preflight for viewers and ingestion.
  - Acceptance: missing tables/columns produce a clear diagnostic before normal work begins.

## Phase 1 — Reproducible testing

- [ ] Create synthetic fixtures for one bat, one session, multiple conditions, two trials, calls, and a pair summary.
  - Acceptance: fixtures contain no real research data and exercise every declared relationship.
- [ ] Add automated tests for initialization, CRUD behavior, constraints, and viewer query results.
  - Acceptance: tests run against temporary databases only and pass in a clean environment.
- [ ] Add ingestion tests for malformed dates, missing required values, boolean encodings, duplicate timestamps, unknown conditions, and partial failures.
  - Acceptance: every invalid case has a deterministic diagnostic and no partial transaction remains.
- [ ] Add export tests.
  - Acceptance: exported rows, columns, nulls, and filter scope exactly match the documented selection.

## Phase 2 — Architecture and schema decisions

- [ ] Decide whether `session_date` and `bat_code` are valid global identifiers.
  - Acceptance: a written multi-experiment/multi-lab use-case review states whether migration is required.
- [ ] Define provenance requirements for raw files, processing code/version, parameters, operator, and time.
  - Acceptance: every derived record can be traced to an immutable input and processing run in a fixture.
- [ ] Define semantics and units for all `call_event` measurements and missing values.
  - Acceptance: the data dictionary has no unresolved field required for analysis, or that field is explicitly quarantined.
- [ ] Decide whether pair summaries belong in a separate normalized table and how they relate to `call_event.pair_id`.
  - Acceptance: the relationship and consistency rules are tested before any schema migration.

## Phase 3 — Ingestion and exports

- [ ] Replace silent `INSERT OR IGNORE` behavior with a documented duplicate policy.
  - Acceptance: exact duplicates, same-time conflicting rows, and re-runs produce expected counts and diagnostics.
- [ ] Use an explicit transaction/rollback boundary and guaranteed connection cleanup.
  - Acceptance: injected failure leaves the destination unchanged and reports the failed group/row.
- [ ] Add input manifests and processing-run records.
  - Acceptance: a run records source path or approved logical identifier, file hash, code version, parameters, counts, and status without leaking secrets.
- [ ] Define export format, scope, units, and metadata.
  - Acceptance: an export is independently interpretable and can be reconciled to the database query that produced it.

## Phase 4 — Deployment preparation

- [ ] Add a reproducible environment file and CI checks.
  - Acceptance: CI runs schema, ingestion, query, export, and safety tests on every reviewed change.
- [ ] Document configuration and data-root policy.
  - Acceptance: a new user can run the application without editing source or guessing a database path.
- [ ] Define backup, migration, rollback, and release procedures.
  - Acceptance: a dry-run on a disposable copy proves backup restoration and migration rollback.
- [ ] Create versioned releases with a changelog and compatibility statement.
  - Acceptance: each release identifies code version, schema version, supported environment, test result, and rollback target.

## Deployment readiness gate

Do not deploy until all of the following are true: a clean environment is reproducible; schema creation and migration are versioned; application startup and ingestion are tested; input/output behavior is validated; provenance and data-integrity safeguards are active; tests are repeatable; backups and rollback have been rehearsed; and a reviewed release artifact exists.
