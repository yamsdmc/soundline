# 0012 — SQLite binding: standard library first, `sqlean.py` fallback

- Status: Proposed. It becomes Accepted when the `sqlite-probe` CI job is green on Linux, macOS and Windows.
- Date: 2026-10-20

## Context

The SQLite store needs the `sqlite-vec` extension (ARC-014, ADR 0005). Loading an extension requires `sqlite3.Connection.enable_load_extension`, which some Python builds omit.

Spike results (`scripts/probe_sqlite.py`, macOS arm64):

| Python build | stdlib `sqlite3` | `sqlean.py` | `apsw` |
|---|---|---|---|
| uv-managed CPython 3.12.15 / 3.13.16 (python-build-standalone) | OK: sqlite-vec v0.1.9, KNN with metadata filter, FTS5 | OK | OK |
| pyenv-built CPython 3.10.12 | **FAIL**: no `enable_load_extension` | OK | — |

This confirms the risk on a real developer machine. It concerns a 3.10 build, below our minimum version, but pyenv builds of 3.12 can lack the feature in the same way, depending on the system SQLite they were compiled against.

## Decision

- Use the standard library `sqlite3` when it can load extensions.
- Otherwise fall back to **`sqlean.py`**, which ships its own SQLite with extension loading and FTS5 and exposes the same DB-API as `sqlite3`. The adapter code is therefore identical for both.
- `sqlean.py` becomes a core dependency when the SQLite adapter lands (M2), so that the fallback needs no user action.
- `soundline doctor` reports which binding is in use.
- **The binding is chosen once per process and never mixed.** Found during M2: sqlite-vec keeps a global pointer to the SQLite API that loaded it. Loading it into a second, different SQLite library (stdlib *and* sqlean in one process) aborts the process (`SIGABRT`, exit code 134) when a connection of the first library is finalized. Reproduced with a ten-line script; guarded by `test_every_database_of_a_process_uses_the_same_sqlite_binding`. Binding selection (`choose_binding`) is a pure check that never loads the extension, so it can be tested in-process.

## Consequences

- One code path, two interchangeable modules, selected at connection time.
- An extra wheel in the core install; to be checked against the size budget once all dependencies are known.
- The SQLite version differs between bindings. The store contract suite runs against both in CI.

## Alternatives considered

- **apsw**: works, but its API differs from DB-API, so the adapter would have to be written twice or wrapped.
- **pysqlite3-binary**: Linux wheels only.
- **Documenting "install a Python with extension support"**: breaks the five-minute quickstart promise.
