"""Events of a streamed answer (GEN-050). Claims are streamed only once verified (GEN-051)."""

from dataclasses import dataclass

from soundline.domain.answers import Answer, Claim
from soundline.domain.chunks import Chunk
from soundline.domain.errors import SoundlineError


@dataclass(frozen=True)
class RetrievalCompleted:
    search_query: str
    evidence: tuple[Chunk, ...]
    """What the model will see, in evidence ID order (E1, E2, ...)."""


@dataclass(frozen=True)
class ClaimVerified:
    claim: Claim
    """With its verified citations only; unsupported claims are never streamed."""


@dataclass(frozen=True)
class AnswerCompleted:
    answer: Answer


@dataclass(frozen=True)
class StreamError:
    error: SoundlineError
    """The stream ends after it."""


type AskEvent = RetrievalCompleted | ClaimVerified | AnswerCompleted | StreamError
