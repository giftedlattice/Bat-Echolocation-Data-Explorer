# How to run

## Scope and safety

The commands below are designed for local, isolated testing. The repository database is a real data artifact. Do not point the ingestion script at the original `batlab.db`, a production path, or a shared database. Copy the database first and use synthetic or explicitly approved input for write tests.

No dependency or environment manifest is present, so the exact original Python version and package versions cannot be reconstructed from this repository.

## 1. Install a supported local runtime

Use a current 64-bit Python 3 installation that includes Tkinter on Windows. Python 3.11 or 3.12 is a reasonable starting point, but the repository does not declare a supported version ceiling.

From PowerShell in the repository root:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pandas numpy matplotlib
python -c "import sqlite3, tkinter, pandas, numpy, matplotlib; print('imports ok')"
```

If `py -3.11` is unavailable, create the environment with the installed interpreter, for example `python -m venv .venv`. If importing `tkinter` fails, install a Python distribution that includes Tcl/Tk; do not work around this by changing application code in this audit phase.

## 2. Confirm the repository files

The expected runtime inputs are:

- `batlab.db`: the current SQLite snapshot.
- `allClickPairDf.csv`: a wide call-event input/export.
- the four viewer scripts and `ingest_call_event.py`.

There is no application configuration file and no environment-variable configuration documented in source. The database path is supplied interactively by each GUI or explicitly on the ingestion command line.

## 3. Make an isolated database copy

This creates a disposable copy outside the repository. The original is not opened for writes.

```powershell
$testRoot = Join-Path $env:TEMP 'DataBase_example-safe-test'
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
Copy-Item .\batlab.db (Join-Path $testRoot 'batlab_test.db') -Force
Copy-Item .\allClickPairDf.csv (Join-Path $testRoot 'allClickPairDf_test.csv') -Force
$testDb = Join-Path $testRoot 'batlab_test.db'
$testCsv = Join-Path $testRoot 'allClickPairDf_test.csv'
```

The copy is still data-bearing. For ingestion development, prefer a new temporary SQLite database created from an approved schema snapshot plus a tiny synthetic CSV, once a reproducible schema script exists.

## 4. First safe local test: read-only GUI startup

Launch one viewer from the activated environment:

```powershell
python .\BatExplorerGUI.py
```

When the file picker appears, select `$testDb`. Confirm that the window opens, bats/dates/conditions populate, a trial can be selected, plots render, and closing the window exits cleanly. Repeat later for the other viewers only after the first viewer is understood.

This startup check was not executed during the audit because no usable Python interpreter was available through the environment tooling and GUI execution would require an interactive desktop session.

## 5. Safe ingestion invocation

Only run this against the disposable copy, and only after backing it up again if you need to compare before/after counts:

```powershell
Copy-Item $testDb (Join-Path $testRoot 'before-ingest.db') -Force
python .\ingest_call_event.py --db $testDb --csv $testCsv --train_or_test Testing
```

The current importer may encounter malformed or missing values in the CSV; it has no complete validation report or explicit rollback path. Treat a failure as an audit result, preserve the disposable copy, and do not retry against an authoritative database.

## 6. Safe database inspection

Use a read-only SQLite client such as DB Browser for SQLite or a read-only connection. Useful queries are included in [TEST_AND_VALIDATION.md](./TEST_AND_VALIDATION.md). Do not execute `DELETE`, `UPDATE`, `DROP`, `ALTER`, `VACUUM`, or migration statements against `batlab.db`.

## 7. Known limitations

- The database schema is embedded only in `batlab.db`; there is no initialization script.
- No migration version is recorded (`PRAGMA user_version` is 0 in the inspected file).
- The source database opened with SQLite foreign-key enforcement off by default; every client must explicitly enable it.
- Dependency versions, Python version support, and expected display-server behavior are undocumented.
