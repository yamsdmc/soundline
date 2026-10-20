"""Soundline: the eval-first RAG engine."""

from soundline.api import Soundline
from soundline.application.ingest import IngestionStatus
from soundline.domain.answers import AbstentionReason, Answer, AnswerStatus, Citation
from soundline.domain.errors import IndexMismatchError, SoundlineError
from soundline.domain.filters import F, Filter, InvalidFilterError
from soundline.domain.hits import Hit

__all__ = [
    "AbstentionReason",
    "Answer",
    "AnswerStatus",
    "Citation",
    "F",
    "Filter",
    "Hit",
    "IndexMismatchError",
    "IngestionStatus",
    "InvalidFilterError",
    "Soundline",
    "SoundlineError",
]
