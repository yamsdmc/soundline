import re
import sqlite3

from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span

_TERM = re.compile(r"\w+")


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
