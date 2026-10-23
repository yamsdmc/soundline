from collections.abc import Sequence
from pathlib import PurePosixPath

from soundline.application.ingest import IngestionReport, IngestionStatus, Ingestor, SourceResult
from soundline.application.ports import DocumentStore, PageReader, SourceReader
from soundline.domain.errors import UnreadableDocumentError

MEDIA_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
}


def ingest_sources(  # noqa: PLR0913  # keyword-only options
    inputs: Sequence[str],
    reader: SourceReader,
    ingestor: Ingestor,
    documents: DocumentStore,
    *,
    delete_missing: bool = False,
    page_reader: PageReader | None = None,
) -> IngestionReport:
    """Ingests files and directories; with `delete_missing` (sync, ING-011), also deletes the
    documents under the inputs whose files disappeared, and nothing outside the inputs."""
    discovery = reader.discover(inputs)
    results = [SourceResult(uri, IngestionStatus.FAILED, "not_found") for uri in discovery.missing]
    results += [_ingest_one(uri, reader, ingestor, page_reader) for uri in discovery.sources]
    if delete_missing:
        present = set(discovery.sources)
        for source in documents.sources():
            if source not in present and _within(source, discovery.scopes):
                ingestor.delete(source)
                results.append(SourceResult(source, IngestionStatus.DELETED))
    return IngestionReport(results)


def _ingest_one(
    uri: str, reader: SourceReader, ingestor: Ingestor, page_reader: PageReader | None
) -> SourceResult:
    media_type = MEDIA_TYPES.get(PurePosixPath(uri).suffix.lower())
    if media_type is None or (media_type == "application/pdf" and page_reader is None):
        return SourceResult(uri, IngestionStatus.SKIPPED, "unsupported_media_type")  # ING-004
    if page_reader is not None and media_type == "application/pdf":
        try:
            pages = page_reader.pages(reader.read(uri))
        except UnreadableDocumentError as error:
            return SourceResult(uri, IngestionStatus.FAILED, error.code)
        if not any(page.strip() for page in pages):  # a scan: never an empty document
            return SourceResult(uri, IngestionStatus.SKIPPED, "no_text_layer")  # ING-026
        return SourceResult(uri, ingestor.ingest_pages(uri, pages))
    try:
        text = reader.read(uri).decode("utf-8")
    except UnicodeDecodeError:
        return SourceResult(uri, IngestionStatus.FAILED, "not_utf8")  # ING-030
    return SourceResult(uri, ingestor.ingest_text(uri, text, media_type=media_type))


def _within(source: str, scopes: Sequence[str]) -> bool:
    return any(source == scope or source.startswith(scope.rstrip("/") + "/") for scope in scopes)
