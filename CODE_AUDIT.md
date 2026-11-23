# Code audit

## Scope and evidence

I read all repository files, inspected all Python modules, examined the Git index and working-tree content, and queried [batlab.db](./batlab.db) through a read-only SQLite connection. No source code, schema, records, or Git history were changed. The environment did not provide a usable Python interpreter, Pylance runtime facts, or a non-interactive GUI session, so Python execution, imports, GUI startup, and ingestion behavior remain unverified.

The following labels distinguish confirmed observations from hypotheses that require a safe test.

## Confirmed findings

| ID | Severity | Affected file(s) | Evidence | Proposed correction | Required validation |
|---|---|---|---|---|---|
| C-01 | High | `batlab.db`, repository root | No schema creation script, migration directory, dependency manifest, or test suite is present. The checked-in database is the only complete schema artifact; `user_version` is 0. | Create a reviewed, versioned schema baseline and migration workflow. Keep the current database as a compatibility fixture until migration tests exist. | Build a fresh temporary database from the baseline and compare tables, columns, indexes, constraints, and representative queries with the fixture. |
| C-02 | High | [ingest_call_event.py](./ingest_call_event.py#L94) | The importer opens a connection, loops through groups, commits only at the end, and closes only on the success path ([lines 106-150](./ingest_call_event.py#L106)). There is no explicit rollback/finally path or error report. | Wrap the operation in an explicit transaction context with rollback and guaranteed close; report rejected groups and counts. Implement only after approval. | Inject a controlled failure in a disposable database and prove zero partial writes plus a useful error report. |
| C-03 | High | [ingest_call_event.py](./ingest_call_event.py#L142) | Rows are inserted with `INSERT OR IGNORE` ([lines 142-147](./ingest_call_event.py#L142)). The schema enforces UNIQUE (`trial_id`, `time_s`), so a duplicate timestamp is silently omitted rather than reported. | Detect and classify duplicate source rows before insertion; use an explicit policy for exact duplicates versus conflicting observations. Avoid silent loss. | Synthetic input with exact and conflicting duplicate timestamps; verify counts, diagnostics, and deterministic policy. |
| C-04 | High | [ingest_call_event.py](./ingest_call_event.py#L78) | Date conversion is `int(float(d))` with no shape/range validation ([lines 78-80](./ingest_call_event.py#L78)). Required-column checking does not validate malformed dates, flags, numeric ranges, or missing `time`. | Validate and normalize each required field before opening the write transaction; reject or quarantine invalid rows with row-level diagnostics. | Cases for malformed date, missing date, non-integral trial, missing time, textual booleans, NaN coordinates, and unknown condition. |
| C-05 | High | [batlab.db](./batlab.db), [ingest_call_event.py](./ingest_call_event.py#L116) | `session.session_date` and `bat.bat_code` are globally unique. The importer looks up sessions only by date and bats only by code ([lines 116-118](./ingest_call_event.py#L116)). There is no experiment, laboratory, institution, researcher, or recording-device identity. | Retain compatibility now, but design an approved multi-study identity model and migration before claiming multi-site support. | Requirements review plus migration tests showing two experiments can share a date and bat code without collision. |
| C-06 | High | [batlab.db](./batlab.db), [ingest_call_event.py](./ingest_call_event.py#L129) | `processing_run` and `binning_scheme` are empty; every inspected trial has null `processing_run_id` and `source_file_path`. The importer accepts a run id but does not create a run or capture source metadata. | Require a processing-run record, immutable input manifest/hash, parameter record, and source identifier for reproducible ingestion. | Re-ingest the same approved input and prove the run metadata identifies the exact source and transformation. |

## Potential bugs and operational risks

| ID | Severity | Affected file(s) | Evidence and status | Proposed correction | Required validation |
|---|---|---|---|---|---|
| P-01 | High | [allClickPairDf.csv](./allClickPairDf.csv), [ingest_call_event.py](./ingest_call_event.py#L97) | The CSV contains 13,072 rows; `time` and `x_call/y_call/z_call` each have 124-125 missing values by direct CSV inspection. `time_s` is NOT NULL, but no missing-value policy exists. Runtime outcome is unverified because the Python environment was unavailable. | Make missingness policy explicit: reject, quarantine, or store missing values only where the schema permits them. | Run the importer on a copy with these rows isolated and verify deterministic diagnostics/rollback. |
| P-02 | High | [allClickPairDf.csv](./allClickPairDf.csv), [ingest_call_event.py](./ingest_call_event.py#L102) | CSV flag columns contain numeric and textual spellings (`0`, `0.5`, `1`, `FALSE`, `TRUE`) in direct inspection, while the database checks flags against `(0,1)`. The importer does not explicitly normalize booleans. Runtime coercion is unverified. | Normalize accepted boolean encodings and reject values such as `0.5` unless scientifically intended. | Synthetic and sampled real-format values against the copy; assert stored SQLite types and values. |
| P-03 | Medium | [Bat3DReconstructionViewer.py](./Bat3DReconstructionViewer.py#L337) | The 3-D viewer conditionally uses a `trajectory_frame` table if it exists, but no such table exists in the inspected schema. The fallback plots call-sampled `x/y/z` as a trajectory. | Document the fallback as a different scientific quantity and add a versioned trajectory schema only when its semantics are approved. | Compare viewer output against known trajectory fixtures and label fallback output clearly. |
| P-04 | Medium | all viewer scripts | Database errors, missing tables/columns, locked files, and malformed databases are not handled with a user-facing recovery path; most queries run during GUI construction or selection. | Add a connection/query error boundary and schema compatibility check before building the UI. | Launch with missing, empty, incompatible, and read-only test databases and verify controlled messages and clean close. |
| P-05 | Medium | [BatExplorerGUI.py](./BatExplorerGUI.py#L512) | “Export filtered CSV” exports `self.calls_df` for the current trial, not all trials in the current list. The UI wording can be read more broadly than the implementation. | Rename the action or export an explicit scope/manifest with the selected trial and filters. | Verify exported row count and metadata against current-trial filters and selected-trials expectations. |
| P-06 | Medium | [ingest_call_event.py](./ingest_call_event.py#L82) | `get_or_create_id` constructs SQL identifiers dynamically and performs lookup-then-insert. Current callers pass constants, so this is not currently user-input SQL injection, but it is race-prone and not a reusable safe API. | Restrict table/column names to an internal allowlist and use conflict-aware inserts where concurrency is relevant. | Unit-test allowed identifiers, invalid identifiers, and concurrent/duplicate ingestion on a temporary database. |
| P-07 | Medium | [BatExplorerCascade.py](./BatExplorerCascade.py#L356) | The cascade viewer filters non-null `x_call` and `y_call` but not `z_call`; it intentionally plots 2-D data, but this differs from the other viewers and is undocumented as a completeness choice. | Clarify the 2-D plotting contract and expose counts of rows omitted from each plot. | Fixture with partial coordinates; verify display and counts. |
| P-08 | Low | repository root | No pinned dependency versions, automated tests, lint/type configuration, release metadata, or CI workflow is present. | Add a small, pinned, reproducible development environment and CI after behavior is stabilized. | Clean-environment setup and repeatable test run on a supported Python/Tk platform. |

## Security and data-safety review

- No credentials, passwords, tokens, or network endpoints were found in the inspected source or configuration files. This does not audit prior Git history or external services.
- The GUIs use parameterized values for user-selected filters. Dynamic SQL fragments are built from fixed facet/column mappings or internal column lists; still keep identifier construction constrained.
- The application opens arbitrary user-selected database paths. A future deployment should enforce an explicit workspace/data-root policy if untrusted files are possible.
- The database and CSV are data-bearing artifacts. Their sensitivity, consent status, retention rules, and redistribution permissions are not documented.
- No destructive SQL was executed. No schema or records were modified.

## Database architecture judgment

Retain the current schema as a read-only compatibility baseline for the next stabilization phase. It has sensible primary keys, several useful unique constraints, foreign keys with deliberate delete actions, and indexes that support observed viewer queries. Change should be planned before production or multi-institution use because the schema is not reproducibly creatable, does not capture populated provenance, treats dates and bat codes as global identifiers, and mixes raw/derived/pair fields in a very wide `call_event` table without a documented semantic contract.

## Recommended order of work

1. Establish a versioned schema baseline and safe fixture strategy.
2. Add dependency/environment metadata and a focused test harness.
3. Make ingestion validate, report, and roll back deterministically.
4. Populate and verify provenance for every processing run.
5. Decide the multi-experiment identity model before changing keys.

