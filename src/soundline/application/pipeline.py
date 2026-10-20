from soundline.application.ports import Embedder, ManifestStore
from soundline.domain.chunking import ChunkingSettings
from soundline.domain.errors import IndexMismatchError
from soundline.domain.manifest import Manifest

PARSER_VERSIONS = {"markdown": "soundline.markdown@1", "html": "soundline.html@1"}
CHUNKER_VERSION = "soundline.structural@1"


def pipeline_manifest(embedder: Embedder, chunking: ChunkingSettings) -> Manifest:
    """Every setting that changes what gets stored, and nothing query-time (STO-002)."""
    return Manifest(
        {
            "parsers": PARSER_VERSIONS,
            "chunker": {
                "strategy": CHUNKER_VERSION,
                "max_tokens": chunking.max_tokens,
                "section_split_level": chunking.section_split_level,
                "tokenizer": getattr(chunking.count_tokens, "__name__", "custom"),
            },
            "embedder": {
                "model_id": embedder.model_id,
                "dimension": embedder.dimension,
                "max_input_tokens": embedder.max_input_tokens,  # changes chunking (ING-041)
            },
        }
    )


def check_pipeline(store: ManifestStore, current: Manifest) -> None:
    """Raises when the index was built differently; an index without manifest is empty."""
    built = store.load()
    if built is not None and built.fingerprint != current.fingerprint:
        changed = ", ".join(built.differences(current))
        raise IndexMismatchError(
            f"this index was built with a different {changed} than the current configuration;"
            " restore the previous configuration, or run `soundline reindex` to rebuild it"
        )
