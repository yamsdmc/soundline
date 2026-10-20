import re
import sqlite3
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import sqlean  # pyright: ignore[reportMissingTypeStubs]
import sqlite_vec

from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span

_TERM = re.compile(r"\w+")


def open_database(
    path: str, bindings: Sequence[ModuleType | Any] = (sqlite3, sqlean)
) -> sqlite3.Connection:
    """Opens a SQLite database with sqlite-vec loaded (ARC-014, ADR 0012).

    Some Python builds compile `sqlite3` without extension loading; the next binding
    (`sqlean.py`, same DB-API) is then used.
    """
    for binding in bindings:
        connection = binding.connect(path)
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(True)
            sqlite_vec.load(connection)
            connection.enable_load_extension(False)
            return connection
    raise RuntimeError("no SQLite binding on this Python can load extensions")


class SqliteLexicalIndex:
    """Lexical index on SQLite FTS5, ranked by BM25 (RET-011)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute(
            "create virtual table if not exists chunk_fts using fts5("
            " text, source unindexed, chunk_id unindexed,"
            " start_offset unindexed, end_offset unindexed,"
            " tokenize = 'unicode61')"
        )

    def add(self, chunk: Chunk) -> None:
        self._db.execute(
            "insert into chunk_fts(text, source, chunk_id, start_offset, end_offset)"
            " values (?, ?, ?, ?, ?)",
            (chunk.text, chunk.source, chunk.id, chunk.span.start, chunk.span.end),
        )

    def search(self, text: str, limit: int) -> list[Chunk]:
        # Each query term is quoted, so user text can never be read as FTS5 syntax (RET-013).
        terms = _TERM.findall(text.lower())
        if not terms:
            return []
        rows = self._db.execute(
            "select source, text, start_offset, end_offset from chunk_fts"
            " where chunk_fts match ? order by bm25(chunk_fts) limit ?",
            (" OR ".join(f'"{term}"' for term in terms), limit),
        )
        return [Chunk(source, body, Span(start, end)) for source, body, start, end in rows]


class SqliteVectorIndex:
    """Exact (brute-force) cosine search with sqlite-vec (STO-041, STO-042)."""

    def __init__(self, connection: sqlite3.Connection, dimension: int) -> None:
        self._db = connection
        self._dimension = dimension
        self._db.execute(
            "create virtual table if not exists chunk_vec using vec0("
            f" embedding float[{dimension}] distance_metric=cosine,"
            " +source text, +text text, +start_offset integer, +end_offset integer)"
        )

    def add(self, chunk: Chunk, vector: tuple[float, ...]) -> None:
        if len(vector) != self._dimension:
            raise ValueError(
                f"vector dimension {len(vector)} differs from the index dimension {self._dimension}"
            )
        self._db.execute(
            "insert into chunk_vec(embedding, source, text, start_offset, end_offset)"
            " values (?, ?, ?, ?, ?)",
            (
                sqlite_vec.serialize_float32(list(vector)),
                chunk.source,
                chunk.text,
                chunk.span.start,
                chunk.span.end,
            ),
        )

    def search(self, vector: tuple[float, ...], limit: int) -> list[Chunk]:
        rows = self._db.execute(
            "select source, text, start_offset, end_offset from chunk_vec"
            " where embedding match ? and k = ? order by distance",
            (sqlite_vec.serialize_float32(list(vector)), limit),
        )
        return [Chunk(source, body, Span(start, end)) for source, body, start, end in rows]
