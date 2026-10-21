"""Soundline: the eval-first RAG engine."""

from soundline.api import Conversation, Soundline
from soundline.application.ask import GenerationSettings
from soundline.application.ingest import IngestionReport, IngestionStatus, SourceResult
from soundline.application.prompts import PromptTemplate
from soundline.domain.answers import AbstentionReason, Answer, AnswerStatus, Citation, QueryInfo
from soundline.domain.conversation import Turn
from soundline.domain.errors import IndexMismatchError, SoundlineError
from soundline.domain.filters import F, Filter, InvalidFilterError
from soundline.domain.hits import Hit
from soundline.domain.usage import Price, Usage

__all__ = [
    "AbstentionReason",
    "Answer",
    "AnswerStatus",
    "Citation",
    "Conversation",
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
    "QueryInfo",
    "Soundline",
    "SoundlineError",
    "SourceResult",
    "Turn",
    "Usage",
]
