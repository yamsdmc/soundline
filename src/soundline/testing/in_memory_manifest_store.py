from soundline.domain.manifest import Manifest


class InMemoryManifestStore:
    def __init__(self) -> None:
        self._manifest: Manifest | None = None

    def load(self) -> Manifest | None:
        return self._manifest

    def save(self, manifest: Manifest) -> None:
        self._manifest = manifest
