import time
from dataclasses import dataclass

from soundline.application.pipeline import check_pipeline
from soundline.application.ports import Embedder, Index
from soundline.domain.errors import SoundlineError
from soundline.domain.manifest import Manifest

DOCUMENTED_SCALE = 100_000  # chunks per corpus on SQLite (STO-042)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def diagnose(index: Index, embedder: Embedder, current: Manifest) -> list[Check]:
    """One real, cheap call per component (CLI-005); never raises."""
    return [_storage(index), _embedder(embedder), _index(index, current)]


def _storage(index: Index) -> Check:
    try:
        return Check("sqlite", True, index.describe())
    except Exception as error:  # a diagnostic reports every failure mode
        return Check("sqlite", False, f"{type(error).__name__}: {error}")


def _embedder(embedder: Embedder) -> Check:
    started = time.perf_counter()
    try:
        vector = embedder.embed_query("Soundline doctor probe")
    except Exception as error:
        return Check("embedder", False, f"{type(error).__name__}: {error}")
    elapsed = (time.perf_counter() - started) * 1000
    return Check(
        "embedder",
        len(vector) == embedder.dimension,
        f"{embedder.model_id}, dimension {embedder.dimension},"
        f" max input {embedder.max_input_tokens} tokens, query embedded in {elapsed:.0f} ms",
    )


def _index(index: Index, current: Manifest) -> Check:
    documents = len(index.documents.sources())
    try:
        check_pipeline(index.manifest, current)
    except SoundlineError as error:
        return Check("index", False, f"{documents} documents; {error}")
    built = "empty, no manifest yet" if index.manifest.load() is None else "compatible"
    return Check("index", True, f"{documents} documents, {built}")
