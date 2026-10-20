import hashlib
from enum import Enum

from soundline.application.pipeline import check_pipeline, pipeline_manifest
from soundline.application.ports import Embedder, Index, StoredDocument
from soundline.domain.chunking import ChunkingSettings, chunk_document
from soundline.domain.chunks import Chunk
from soundline.domain.filters import Metadata
from soundline.domain.markdown import parse_markdown


class IngestionStatus(Enum):
    ADDED = "added"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


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
        self, source: str, text: str, metadata: Metadata | None = None
    ) -> IngestionStatus:
        check_pipeline(self._index.manifest, self._manifest)  # STO-010
        revision = hashlib.sha256(text.encode()).hexdigest()
        previous = self._documents.get(source)
        if previous and previous.revision == revision:
            return IngestionStatus.UNCHANGED  # ING-007: no parse, no embedding, no write

        document = parse_markdown(text)
        chunks = [
            Chunk(
                source=source,
                text=document.text[planned.span.start : planned.span.end],
                span=planned.span,
                metadata=metadata or {},
                section_path=planned.section_path,
            )
            for planned in chunk_document(
                document,
                self._chunking.max_tokens,
                self._chunking.count_tokens,
                self._chunking.section_split_level,
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
