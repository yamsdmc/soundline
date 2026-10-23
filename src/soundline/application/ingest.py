import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from soundline.application.pipeline import check_pipeline, pipeline_manifest
from soundline.application.ports import Embedder, Index, StoredDocument
from soundline.domain.chunking import ChunkingSettings, chunk_document
from soundline.domain.chunks import Chunk
from soundline.domain.documents import ParsedDocument
from soundline.domain.filters import Metadata
from soundline.domain.html import parse_html
from soundline.domain.markdown import parse_markdown
from soundline.domain.pdf import PAGE_BREAK, pages_within, parse_pdf_pages


class IngestionStatus(Enum):
    ADDED = "added"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    DELETED = "deleted"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceResult:
    source: str
    status: IngestionStatus
    reason: str | None = None
    """Stable code for SKIPPED and FAILED, e.g. `unsupported_media_type`, `not_utf8`."""


@dataclass(frozen=True)
class IngestionReport:
    results: list[SourceResult]

    def count(self, status: IngestionStatus) -> int:
        return sum(result.status is status for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "results": [
                {"source": r.source, "status": r.status.value, "reason": r.reason}
                for r in self.results
            ]
        }


PARSERS: dict[str, Callable[[str], ParsedDocument]] = {
    "text/markdown": parse_markdown,
    "text/plain": parse_markdown,  # plain text is valid Markdown
    "text/html": parse_html,
}


class Ingestor:
    def __init__(self, index: Index, embedder: Embedder, chunking: ChunkingSettings) -> None:
        self._index = index
        self._manifest = pipeline_manifest(embedder, chunking)
        self._documents = index.documents
        self._lexical = index.lexical
        self._dense = index.dense
        self._embedder = embedder
        self._chunking = chunking

    def ingest_text(
        self,
        source: str,
        text: str,
        metadata: Metadata | None = None,
        media_type: str = "text/markdown",
    ) -> IngestionStatus:
        return self._index_document(source, text, lambda: PARSERS[media_type](text), metadata)

    def ingest_pages(
        self, source: str, pages: Sequence[str], metadata: Metadata | None = None
    ) -> IngestionStatus:
        """A paged document, such as a PDF's text layer, one string per page (ING-025)."""
        return self._index_document(
            source, PAGE_BREAK.join(pages), lambda: parse_pdf_pages(pages), metadata
        )

    def _index_document(
        self,
        source: str,
        raw: str,
        parse: Callable[[], ParsedDocument],
        metadata: Metadata | None,
    ) -> IngestionStatus:
        check_pipeline(self._index.manifest, self._manifest)  # STO-010
        revision = hashlib.sha256(raw.encode()).hexdigest()
        previous = self._documents.get(source)
        if previous and previous.revision == revision:
            return IngestionStatus.UNCHANGED  # ING-007: no parse, no embedding, no write

        document = parse()
        chunks = [
            Chunk(
                source=source,
                text=document.text[planned.span.start : planned.span.end],
                span=planned.span,
                metadata=metadata or {},
                section_path=planned.section_path,
                pages=pages_within(planned.span, document.pages),  # ING-047
            )
            for planned in chunk_document(
                document,
                self._chunking.max_tokens,
                self._chunking.count_tokens,
                self._chunking.section_split_level,
                also_fits=self._fits_embedder,  # ING-041, ING-072
            )
        ]
        vectors = self._embedder.embed_documents([chunk.text for chunk in chunks])

        with self._index.transaction():  # readers see the old revision or the new one (STO-020)
            self._lexical.remove(source)
            self._dense.remove(source)
            for chunk, vector in zip(chunks, vectors, strict=True):
                self._lexical.add(chunk)
                self._dense.add(chunk, vector)
            self._documents.save(StoredDocument(source, revision, document.text))
            self._index.manifest.save(self._manifest)  # STO-001
        return IngestionStatus.UPDATED if previous else IngestionStatus.ADDED

    def _fits_embedder(self, text: str) -> bool:
        return self._embedder.count_tokens(text) <= self._embedder.max_input_tokens

    def delete(self, source: str) -> None:
        with self._index.transaction():
            self._lexical.remove(source)
            self._dense.remove(source)
            self._documents.remove(source)
