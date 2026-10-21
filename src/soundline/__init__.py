"""Soundline: the eval-first RAG engine."""

from soundline.api import Soundline
from soundline.application.ask import GenerationSettings
from soundline.application.ingest import IngestionReport, IngestionStatus, SourceResult
from soundline.application.prompts import PromptTemplate
from soundline.domain.answers import AbstentionReason, Answer, AnswerStatus, Citation
from soundline.domain.errors import IndexMismatchError, SoundlineError
from soundline.domain.filters import F, Filter, InvalidFilterError
from soundline.domain.hits import Hit
from soundline.domain.usage import Price, Usage

__all__ = [
    "AbstentionReason",
    "Answer",
    "AnswerStatus",
    "Citation",
    "F",
    "Filter",
    "GenerationSettings",
    "Hit",
    "IndexMismatchError",
    "IngestionReport",
    "IngestionStatus",
    "InvalidFilterError",
    "Price",
    "PromptTemplate",
    "Soundline",
    "SoundlineError",
    "SourceResult",
    "Usage",
]
