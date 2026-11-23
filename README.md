# DataBase_example

## Purpose

This repository is a small Python/SQLite research-data prototype for exploring bat echolocation call events. It contains an ingestion script that maps a wide CSV export into a normalized SQLite database and several Tkinter/Matplotlib desktop viewers for browsing trials, filtering calls, plotting call positions and trajectories, and exporting the currently filtered calls.

The code does not contact a network service, call an external API, control hardware, or provide a web service. The scientific source pipeline that produced the CSV is not included, so the meaning and provenance of several measurements cannot be established from this repository alone.

## Current architecture

```text
allClickPairDf.csv
        |
        v
ingest_call_event.py -- pandas validation/mapping -- SQLite writes
        |
        v
batlab.db
  bat / session / condition / trial
        |
        +--> call_event
        +--> click_pair (currently empty)
        +--> processing_run / binning_scheme (currently empty)
        |
        +--> BatExplorerGUI.py           filters, plots, table, CSV export
        +--> BatExplorerCascade.py       reorderable cascading filters and plots
        +--> BatTrajectoryViewer_newschema.py  3-D call-position viewer
        +--> Bat3DReconstructionViewer.py      audio/video/combined 3-D viewer
```

All four viewers open a user-selected SQLite file. They enable `PRAGMA foreign_keys = ON` on their own connection and perform read-only application queries. The viewers do not create tables or write records. The GUI export in `BatExplorerGUI.py` writes a user-selected CSV containing the current trial's filtered `call_event` rows.

## Repository snapshot inspected

The checked-in database contains eight application tables: `bat`, `session`, `condition`, `trial`, `call_event`, `processing_run`, `binning_scheme`, and `click_pair`. At audit time it contained 5 bats, 51 sessions, 7 conditions, 644 trials, and 5,124 call events. The latter three supporting tables were empty. The source CSV contains 13,072 data rows, 5 bats, 51 dates, and 7 condition codes; the repository does not document whether it is intended to be a complete input for the checked-in database.

## Dependencies

The source imports:

- Python standard library: `sqlite3`, `tkinter`, `os`, and `argparse`.
- Third-party packages: `pandas`, `numpy`, and `matplotlib`.
- A Tk-capable Python installation is required for the desktop viewers. No `requirements.txt`, `pyproject.toml`, `environment.yml`, lockfile, or supported Python-version policy is present.

## Entry points

Run from the repository root after installing dependencies:

```powershell
python .\BatExplorerGUI.py
python .\BatExplorerCascade.py
python .\BatTrajectoryViewer_newschema.py
python .\Bat3DReconstructionViewer.py
python .\ingest_call_event.py --db <safe-test-db> --csv <input-csv> [--processing_run_id <id>] [--train_or_test <label>]
```

Each viewer opens a file picker. Select a disposable test copy of the database, never the only authoritative copy. See [HOW_TO_RUN.md](./HOW_TO_RUN.md) for the safe setup and first test.

## Development status

This is an exploratory prototype, not a deployment-ready research data system. The database snapshot is usable for read-only exploration, but database creation is not reproducible from source, ingestion validation is incomplete, transaction behavior is not tested, provenance fields are unpopulated, and no automated tests or release process are included. Do not refactor code, change the schema, or run migrations until the next development phase is approved.

## Documentation map

- [HOW_TO_RUN.md](./HOW_TO_RUN.md): environment setup and safe local execution.
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md): observed SQLite schema, relationships, and indexes.
- [CODE_AUDIT.md](./CODE_AUDIT.md): confirmed findings, risks, and recommendations.
- [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md): phased work plan with acceptance criteria.
- [TEST_AND_VALIDATION.md](./TEST_AND_VALIDATION.md): safe verification procedures.
- [DATA_DICTIONARY.md](./DATA_DICTIONARY.md): field meanings, units, values, and sources.
- [AGENTS.md](./AGENTS.md): permanent development and data-safety instructions.
