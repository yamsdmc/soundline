import json
import re
import sqlite3
from collections.abc import Sequence
from functools import cache
from types import ModuleType
from typing import Any

import sqlite_vec

from soundline.application.ports import StoredDocument
from soundline.domain.chunks import Chunk
from soundline.domain.filters import And, Compare, Exists, Filter, Member, Not, Or, Scalar
from soundline.domain.manifest import Manifest
from soundline.domain.quotes import Span

_TERM = re.compile(r"\w+")

type _Sql = tuple[str, list[object]]


def filter_to_sql(condition: Filter, column: str) -> _Sql:
    """Translates a filter into a parameterized SQL boolean over a JSON metadata column.

    Mirrors `soundline.domain.filters.matches` exactly (checked by a property test):
    every leaf checks the JSON type first, because SQLite orders text above numbers,
    and is wrapped in coalesce(…, 0) so that NULL never leaks into `not`.
    """
    match condition:
        case And(items) | Or(items):
            parts = [filter_to_sql(item, column) for item in items]
            joiner = " and " if isinstance(condition, And) else " or "
            return joiner.join(f"({sql})" for sql, _ in parts), [p for _, ps in parts for p in ps]
        case Not(item):
            sql, params = filter_to_sql(item, column)
            return f"not ({sql})", params
        case Exists(key):
            return f"json_type({column}, ?) is not null", [_path(key)]
        case Member(op, key, values):
            if not values:
                return ("0" if op == "in" else _exists(column, key)), (
                    [] if op == "in" else [_path(key)]
                )
            parts = [_equal(column, key, value) for value in values]
            sql = " or ".join(f"({sql})" for sql, _ in parts)
            params = [p for _, ps in parts for p in ps]
            if op == "in":
                return sql, params
            return f"{_exists(column, key)} and not ({sql})", [_path(key), *params]
        case Compare("eq", key, value):
            return _equal(column, key, value)
        case Compare("ne", key, value):
            sql, params = _equal(column, key, value)
            return f"{_exists(column, key)} and not ({sql})", [_path(key), *params]
        case Compare(op, key, value):
            types = _json_types(value)
            sql = (
                f"coalesce(json_type({column}, ?) in ({_placeholders(types)})"
                f" and json_extract({column}, ?) {_ORDERINGS[op]} ?, 0)"
            )
            return sql, [_path(key), *types, _path(key), value]


_ORDERINGS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def _equal(column: str, key: str, value: Scalar) -> _Sql:
    types = _json_types(value)
    sql = (
        f"coalesce((json_type({column}, ?) in ({_placeholders(types)})"
        f" and json_extract({column}, ?) = ?)"
        f" or (json_type({column}, ?) = 'array' and exists("
        f"select 1 from json_each({column}, ?) as item"
        f" where item.type in ({_placeholders(types)}) and item.value = ?)), 0)"
    )
    path = _path(key)
    return sql, [path, *types, path, value, path, path, *types, value]


def _exists(column: str, key: str) -> str:
    return f"json_type({column}, ?) is not null"


def _json_types(value: Scalar) -> list[str]:
    if isinstance(value, bool):
        return ["true", "false"]
    if isinstance(value, int | float):
        return ["integer", "real"]
    return ["text"]


def _placeholders(values: Sequence[object]) -> str:
    return ", ".join("?" for _ in values)


def _path(key: str) -> str:
    if '"' in key:
        raise ValueError(f"metadata keys cannot contain double quotes: {key!r}")
    return f'$."{key}"'


def choose_binding(bindings: Sequence[ModuleType | Any]) -> ModuleType | Any:
    """The first binding able to load extensions (ARC-014, ADR 0012).

    Some Python builds compile `sqlite3` without extension loading; `sqlean.py`
    (its own SQLite, same DB-API) is then used.
    """
    for binding in bindings:
        probe = binding.connect(":memory:")
        capable = hasattr(probe, "enable_load_extension")
        probe.close()
        if capable:
            return binding
    raise RuntimeError("no SQLite binding on this Python can load extensions")


def _available_bindings() -> list[ModuleType]:
    bindings: list[ModuleType] = [sqlite3]
    try:
        import sqlean  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs]
    except ImportError:  # not installed on Windows, see ADR 0012
        return bindings
    return [*bindings, sqlean]


@cache
def _process_binding() -> ModuleType | Any:
    # Chosen once per process: sqlite-vec keeps a global pointer to the SQLite API that
    # loaded it, so loading it into two different SQLite libraries aborts the process.
    return choose_binding(_available_bindings())


def open_database(path: str) -> sqlite3.Connection:
    """Opens a SQLite database with sqlite-vec loaded."""
    connection = _process_binding().connect(path)
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    connection.enable_load_extension(False)
    return connection


_COLUMNS = "source, text, start_offset, end_offset, metadata"


def _chunk(row: tuple[str, str, int, int, str]) -> Chunk:
    source, text, start, end, metadata = row
    return Chunk(source, text, Span(start, end), json.loads(metadata))


def _where(condition: Filter | None) -> _Sql:
    if condition is None:
        return "1", []
    return filter_to_sql(condition, "metadata")


class SqliteLexicalIndex:
    """Lexical index on SQLite FTS5, ranked by BM25 (RET-011)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute(
            "create virtual table if not exists chunk_fts using fts5("
            " text, source unindexed, chunk_id unindexed,"
            " start_offset unindexed, end_offset unindexed, metadata unindexed,"
            " tokenize = 'unicode61')"
        )

    def add(self, chunk: Chunk) -> None:
        self._db.execute(
            "insert into chunk_fts(text, source, chunk_id, start_offset, end_offset, metadata)"
            " values (?, ?, ?, ?, ?, ?)",
            (
                chunk.text,
                chunk.source,
                chunk.id,
                chunk.span.start,
                chunk.span.end,
                json.dumps(chunk.metadata),
            ),
        )

    def remove(self, source: str) -> None:
        self._db.execute("delete from chunk_fts where source = ?", (source,))

    def search(self, text: str, limit: int, filter: Filter | None = None) -> list[Chunk]:
        # Each query term is quoted, so user text can never be read as FTS5 syntax (RET-013).
        terms = _TERM.findall(text.lower())
        if not terms:
            return []
        where, params = _where(filter)
        rows = self._db.execute(
            f"select {_COLUMNS} from chunk_fts"
            f" where chunk_fts match ? and ({where}) order by bm25(chunk_fts) limit ?",
            [" OR ".join(f'"{term}"' for term in terms), *params, limit],
        )
        return [_chunk(row) for row in rows]


class SqliteVectorIndex:
    """Exact (brute-force) cosine search with sqlite-vec (STO-041, STO-042).

    Unfiltered searches use vec0's KNN. Filtered searches compute exact distances over
    the rows matching the filter, because KNN constraints cannot see auxiliary columns
    (STO-043); this keeps RET-041: the k nearest *matching* chunks, however far.
    """

    def __init__(self, connection: sqlite3.Connection, dimension: int) -> None:
        self._db = connection
        self._dimension = dimension
        self._db.execute(
            "create virtual table if not exists chunk_vec using vec0("
            f" embedding float[{dimension}] distance_metric=cosine,"
            " +source text, +text text, +start_offset integer, +end_offset integer,"
            " +metadata text)"
        )

    def add(self, chunk: Chunk, vector: tuple[float, ...]) -> None:
        if len(vector) != self._dimension:
            raise ValueError(
                f"vector dimension {len(vector)} differs from the index dimension {self._dimension}"
            )
        self._db.execute(
            f"insert into chunk_vec(embedding, {_COLUMNS}) values (?, ?, ?, ?, ?, ?)",
            (
                sqlite_vec.serialize_float32(list(vector)),
                chunk.source,
                chunk.text,
                chunk.span.start,
                chunk.span.end,
                json.dumps(chunk.metadata),
            ),
        )

    def remove(self, source: str) -> None:
        self._db.execute("delete from chunk_vec where source = ?", (source,))

    def search(
        self, vector: tuple[float, ...], limit: int, filter: Filter | None = None
    ) -> list[Chunk]:
        query = sqlite_vec.serialize_float32(list(vector))
        if filter is None:
            rows = self._db.execute(
                f"select {_COLUMNS} from chunk_vec"
                " where embedding match ? and k = ? order by distance",
                (query, limit),
            )
        else:
            where, params = _where(filter)
            rows = self._db.execute(
                f"select {_COLUMNS} from chunk_vec where {where}"
                " order by vec_distance_cosine(embedding, ?) limit ?",
                [*params, query, limit],
            )
        return [_chunk(row) for row in rows]


class SqliteDocumentStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute(
            "create table if not exists document("
            " source text primary key, revision text not null, text text not null)"
        )

    def get(self, source: str) -> StoredDocument | None:
        row = self._db.execute(
            "select source, revision, text from document where source = ?", (source,)
        ).fetchone()
        return StoredDocument(*row) if row else None

    def save(self, document: StoredDocument) -> None:
        self._db.execute(
            "insert or replace into document(source, revision, text) values (?, ?, ?)",
            (document.source, document.revision, document.text),
        )

    def remove(self, source: str) -> None:
        self._db.execute("delete from document where source = ?", (source,))

    def sources(self) -> list[str]:
        return [row[0] for row in self._db.execute("select source from document order by source")]


class SqliteManifestStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute(
            "create table if not exists manifest(id integer primary key check (id = 1),"
            " components text not null)"
        )

    def load(self) -> Manifest | None:
        row = self._db.execute("select components from manifest where id = 1").fetchone()
        return Manifest.from_json(row[0]) if row else None

    def save(self, manifest: Manifest) -> None:
        self._db.execute(
            "insert or replace into manifest(id, components) values (1, ?)", (manifest.to_json(),)
        )
