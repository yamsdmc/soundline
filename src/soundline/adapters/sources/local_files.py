from collections.abc import Sequence
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from soundline.application.ports import Discovery


class LocalFiles:
    """Reads sources from the local filesystem, identified by file:// URIs (ING-008)."""

    def discover(self, inputs: Sequence[str]) -> Discovery:
        sources: set[str] = set()
        for given in inputs:
            path = Path(given).resolve()
            if path.is_file():
                sources.add(path.as_uri())
            elif path.is_dir():
                sources.update(_walk(path))
        scopes = [Path(given).resolve().as_uri() for given in inputs]
        return Discovery(sorted(sources), scopes)

    def read(self, uri: str) -> bytes:
        return Path(url2pathname(unquote(urlparse(uri).path))).read_bytes()  # 3.12: no from_uri


def _walk(directory: Path) -> set[str]:
    found: set[str] = set()
    for entry in directory.iterdir():
        if entry.name.startswith(".") or entry.is_symlink():  # ING-002, ING-006
            continue
        if entry.is_dir():
            found.update(_walk(entry))
        elif entry.is_file():
            found.add(entry.as_uri())
    return found
