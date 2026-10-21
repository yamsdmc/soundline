"""Public test doubles: deterministic fakes for Soundline's ports (API-020)."""

from soundline.testing.hashing_embedder import HashingEmbedder
from soundline.testing.in_memory_document_store import InMemoryDocumentStore
from soundline.testing.in_memory_index import InMemoryIndex
from soundline.testing.in_memory_manifest_store import InMemoryManifestStore
from soundline.testing.in_memory_run_store import InMemoryRunStore
from soundline.testing.in_memory_vector_index import InMemoryVectorIndex
from soundline.testing.scripted_language_model import ScriptedLanguageModel

__all__ = [
    "HashingEmbedder",
    "InMemoryDocumentStore",
    "InMemoryIndex",
    "InMemoryManifestStore",
    "InMemoryRunStore",
    "InMemoryVectorIndex",
    "ScriptedLanguageModel",
]
