# Instructions for future Codex development

## Scientific reproducibility

- Treat every measurement definition, unit, coordinate frame, filter, and missing-value rule as part of the scientific contract.
- Do not infer a field's scientific meaning from a filename or a plausible abbreviation. Mark it ambiguous and ask for an authoritative definition.
- Preserve input identifiers, raw values, processing parameters, code version, and source-file hashes wherever provenance is required.
- Keep synthetic fixtures separate from research data and label every result as observed, derived, or unverified.

## Database integrity

- Never modify the authoritative SQLite file during exploration or testing.
- Use a temporary database or disposable copy for all write, ingestion, rollback, constraint, and migration tests.
- Enable and assert `PRAGMA foreign_keys = ON` on every connection.
- Do not use silent conflict handling for research records unless the duplicate policy is documented, tested, and reported.
- Do not add, remove, rename, or alter schema objects without an approved migration plan, backup, forward test, rollback/restore test, and compatibility review.

## Change discipline

- Make small, reviewable changes with a clear acceptance criterion.
- Preserve existing source files and behavior until the requested change is explicit.
- Before changing an importer, reproduce the behavior with a synthetic fixture and add a focused validation that would fail before the fix.
- Do not claim a test passed unless it was actually run successfully; distinguish static inspection from runtime evidence.
- Keep dependency versions, supported Python versions, schema versions, and test commands documented and reproducible.

## Safe GitHub workflow

- Inspect `git status`, the diff, tracked files, and ignore rules before editing.
- Never commit, push, merge, rewrite history, or open/modify a pull request unless explicitly requested.
- Do not commit credentials, tokens, connection strings, local environment files, virtual environments, caches, generated exports, temporary databases, or unapproved research data.
- For this repository, review whether `*.db`, `*.sqlite*`, generated CSV exports, `*.pyc`, `__pycache__/`, `.venv/`, `.env*`, and local IDE files belong in `.gitignore`; do not remove currently tracked files without explicit approval.
- Review the complete diff after every documentation or code change.

## Deployment gate

Do not recommend deployment until a clean environment can be reproduced, the database can be created or migrated from versioned artifacts, startup and ingestion are tested, outputs are validated, provenance and integrity safeguards are active, backups and rollback are rehearsed, and a versioned release has passed review.

## Default operating rule

When a requested action could alter source code, schema, records, production services, or Git history, pause and obtain explicit authorization if that action is not already clearly within the task. Prefer read-only inspection and reversible, isolated validation.
