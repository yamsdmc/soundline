"""Model calls cached by input, for reproducible evaluation runs (EVL-061)."""

import hashlib
import json

from soundline.application.ports import (
    Generation,
    GenerationCache,
    GenerationRequest,
    LanguageModel,
)


class CachedLanguageModel:
    """Answers an identical request from the cache: same output, same recorded usage, no
    model cost. The key covers the model and everything it is sent."""

    def __init__(self, inner: LanguageModel, cache: GenerationCache) -> None:
        self._inner = inner
        self._cache = cache

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def generate(self, request: GenerationRequest) -> Generation:
        key = _key(self._inner.model_id, request)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        generation = self._inner.generate(request)
        self._cache.put(key, generation)
        return generation


def _key(model_id: str, request: GenerationRequest) -> str:
    material = {
        "model": model_id,
        "system": request.system,
        "prompt": request.prompt,
        "output": {"name": request.output.name, "schema": request.output.schema},
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
