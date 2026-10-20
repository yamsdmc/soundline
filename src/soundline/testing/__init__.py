"""Public test doubles: deterministic fakes for Soundline's ports (API-020)."""

from soundline.testing.hashing_embedder import HashingEmbedder
from soundline.testing.in_memory_index import InMemoryIndex
from soundline.testing.scripted_language_model import ScriptedLanguageModel

__all__ = ["HashingEmbedder", "InMemoryIndex", "ScriptedLanguageModel"]
