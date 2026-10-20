from collections.abc import Sequence

from soundline.application.ingest import IngestionReport, IngestionStatus, Ingestor, SourceResult
from soundline.application.ports import DocumentStore, SourceReader

SUPPORTED_SUFFIXES = (".md", ".markdown", ".txt")  # more formats arrive with their parsers


def ingest_sources(
    inputs: Sequence[str],
    reader: SourceReader,
    ingestor: Ingestor,
    documents: DocumentStore,
    *,
    delete_missing: bool = False,
) -> IngestionReport:
    """Ingests files and directories; with `delete_missing` (sync, ING-011), also deletes the
    documents under the inputs whose files disappeared, and nothing outside the inputs."""
    discovery = reader.discover(inputs)
    results = [_ingest_one(uri, reader, ingestor) for uri in discovery.sources]
    if delete_missing:
        present = set(discovery.sources)
        for source in documents.sources():
            if source not in present and _within(source, discovery.scopes):
                ingestor.delete(source)
                results.append(SourceResult(source, IngestionStatus.DELETED))
    return IngestionReport(results)


def _ingest_one(uri: str, reader: SourceReader, ingestor: Ingestor) -> SourceResult:
    if not uri.lower().endswith(SUPPORTED_SUFFIXES):
        return SourceResult(uri, IngestionStatus.SKIPPED, "unsupported_media_type")  # ING-004
    try:
        text = reader.read(uri).decode("utf-8")
    except UnicodeDecodeError:
        return SourceResult(uri, IngestionStatus.FAILED, "not_utf8")  # ING-030
    return SourceResult(uri, ingestor.ingest_text(uri, text))


def _within(source: str, scopes: Sequence[str]) -> bool:
    return any(source == scope or source.startswith(scope.rstrip("/") + "/") for scope in scopes)
