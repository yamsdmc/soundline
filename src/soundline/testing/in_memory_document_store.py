from soundline.application.ports import StoredDocument


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, StoredDocument] = {}

    def get(self, source: str) -> StoredDocument | None:
        return self._documents.get(source)

    def save(self, document: StoredDocument) -> None:
        self._documents[document.source] = document

    def remove(self, source: str) -> None:
        self._documents.pop(source, None)

    def sources(self) -> list[str]:
        return sorted(self._documents)
