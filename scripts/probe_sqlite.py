"""Spike for ARC-014: can each SQLite binding load sqlite-vec and use FTS5 on this platform?

Run in CI on every OS of the matrix. Prints one line per binding and exits with 1
when no binding works, which would break the local-first promise on that platform.
"""

import importlib
import platform
import sys
from types import ModuleType


def probe(binding: ModuleType) -> str:
    import sqlite_vec  # noqa: PLC0415  # only installed for the probe run

    connection = binding.connect(":memory:")
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    connection.enable_load_extension(False)
    connection.execute("create virtual table v using vec0(embedding float[2], kind text)")
    connection.execute("insert into v(rowid, embedding, kind) values (1, '[1,0]', 'a')")
    rows = connection.execute(
        "select rowid from v where embedding match '[1,0.1]' and k = 1 and kind = 'a'"
    ).fetchall()
    connection.execute("create virtual table f using fts5(body)")
    version = connection.execute("select vec_version()").fetchone()[0]
    return f"OK (sqlite-vec {version}, knn {rows}, fts5 yes)"


def main() -> int:
    print(f"{platform.system()} {platform.machine()} python {sys.version.split()[0]}")
    working = 0
    for name in ("sqlite3", "sqlean"):
        try:
            outcome = probe(importlib.import_module(name))
            working += 1
        except Exception as error:  # a spike reports every failure mode
            outcome = f"FAIL {type(error).__name__}: {error}"
        print(f"  {name:8} {outcome}")
    return 0 if working else 1


if __name__ == "__main__":
    sys.exit(main())
