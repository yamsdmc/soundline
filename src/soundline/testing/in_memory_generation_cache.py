from soundline.application.ports import Generation


class InMemoryGenerationCache:
    """Fake generation cache: a dictionary."""

    def __init__(self) -> None:
        self._generations: dict[str, Generation] = {}

    def get(self, key: str) -> Generation | None:
        return self._generations.get(key)

    def put(self, key: str, generation: Generation) -> None:
        self._generations[key] = generation
