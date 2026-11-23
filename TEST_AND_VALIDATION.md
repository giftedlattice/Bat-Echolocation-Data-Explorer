# Test and validation procedures

## Safety rules

Run all write tests against a new temporary SQLite database or a disposable copy. Use synthetic data unless the data owner explicitly approves a fixture. Never run these procedures against a production path or the only copy of [batlab.db](./batlab.db). Do not use `DROP`, `DELETE`, `UPDATE`, `ALTER`, migration scripts, or cleanup SQL on the authoritative database.

The procedures below are a validation design, not evidence that the application has passed them. Runtime execution was not completed during this audit.

## Test setup

1. Create a temporary directory and copy the database as described in [HOW_TO_RUN.md](./HOW_TO_RUN.md).
2. Record the source and destination paths, database checksum, SQLite version, Python version, package versions, and test timestamp.
3. If a fresh schema script becomes available, prefer a newly created empty test database. Until then, use a copy of the inspected fixture and label fixture-dependent tests.
4. Enable foreign keys on every test connection and assert the setting immediately after connecting:

```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_keys;
```

The second statement must return `1`.

## Startup and schema checks

- Launch each viewer with the disposable database. Verify the window opens, lookup controls populate, an empty result is handled, a trial can be selected, and close releases the connection.
- Verify required tables with `sqlite_master` and compare the result to [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md).
- Run `PRAGMA integrity_check;` and require `ok`.
- Run `PRAGMA foreign_key_check;` and require zero rows.
- Run `PRAGMA user_version;` and record the result. A value of 0 is currently observed and means no migration versioning is present.
- Inspect every `CREATE TABLE` and index definition. Fail the test if an expected key, unique constraint, check constraint, foreign key, or delete action changes unexpectedly.

## CRUD and constraint checks on a temporary database

Use synthetic IDs and values. Insert a valid bat, session, condition, trial, and call event in parent-to-child order. Retrieve each row by primary key and verify values and SQLite types. Update an allowed nullable field and verify the update. Do not test deletion against the authoritative database.

On the disposable database, separately verify:

- duplicate `bat_code`, `session_date`, `cond_code`, trial natural key, `(trial_id,time_s)`, `(trial_id,call_num)`, and `(trial_id,pair_id)` are rejected or handled exactly as documented;
- a child with a missing parent is rejected when foreign keys are enabled;
- deleting a trial cascades only to its declared `call_event` and `click_pair` children;
- deleting a referenced bat or condition is restricted;
- deleting a processing run nulls `trial.processing_run_id`;
- nullable measurements remain distinguishable from zero.

## Ingestion checks

Prepare small synthetic CSV files with:

1. one valid row;
2. multiple rows in one trial with out-of-order times;
3. missing required headers;
4. malformed and out-of-range dates;
5. missing `time`, malformed trial, and missing bat/condition;
6. `good_call`/`behind` values `0`, `1`, `TRUE`, `FALSE`, `0.5`, and blank;
7. duplicate exact rows and conflicting rows at the same `(trial,time)`;
8. an invalid `processing_run_id`;
9. an injected failure after at least one group has been processed.

For each case, record exit status, diagnostics, inserted counts, skipped/rejected counts, and destination row counts. The expected safe behavior is deterministic validation before writes or a transaction that fully rolls back on error. The current importer does not yet guarantee this behavior; these are acceptance tests for the next phase.

## Retrieval and export checks

Run each viewer query with known synthetic values and compare returned rows to direct SQL. Test each filter independently and in combination: bat, date, condition, trial, trip, good-call, front/behind, and pair. Verify ordering by `time_s` and handling of null coordinates.

For export, select one trial and a known filter set. Verify that the CSV columns, row count, order, null representation, and values match the current-trial query. Explicitly verify whether the product requirement is current-trial export or all-selected-trials export; the current GUI implementation exports only `self.calls_df` for the current trial.

## Transaction rollback check

On a disposable database, begin the importer or a dedicated test transaction, insert a valid parent and child, force a constraint error, issue rollback, and verify all writes from that transaction are absent. Repeat with an error in a later ingestion group. Record whether the connection is closed and whether a subsequent connection sees the pre-test state.

## Migration compatibility check

There are currently no migration scripts to execute. Before introducing one:

1. Snapshot the fixture schema and counts.
2. Back up the disposable database.
3. Apply the migration only to the disposable copy.
4. Run integrity, foreign-key, key, null, count, and representative-query checks.
5. Test rollback or restore from backup.
6. Compare exports before and after for an unchanged dataset.

Acceptance requires a documented forward path, a tested rollback/restore path, and a compatibility statement. Never infer migration success from a script exit code alone.
