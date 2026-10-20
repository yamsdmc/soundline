import math
from collections.abc import Iterable, Sequence

from fastembed import TextEmbedding

from soundline.application.ports import Vector


def _unit(values: Iterable[float]) -> Vector:
    vector = tuple(float(x) for x in values)
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return tuple(x / norm for x in vector)


class FastembedEmbedder:
    """Local ONNX embeddings, no API key (CFG-020).

    `query_embed` and `passage_embed` apply each model's own asymmetric prefixes
    (e.g. `query:` / `passage:` for E5 models).
    """

    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name)

    @property
    def dimension(self) -> int:
        return self._model.embedding_size

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [_unit(vector) for vector in self._model.passage_embed(list(texts))]

    def embed_query(self, text: str) -> Vector:
        return _unit(next(iter(self._model.query_embed(text))))
