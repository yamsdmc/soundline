"""Evaluation use cases (docs/spec/06-evaluation.md)."""

import difflib
import re
from pathlib import PurePosixPath

from soundline.application.ports import DocumentStore
from soundline.domain.datasets import Dataset, DatasetError, RelevantQuote
from soundline.domain.evaluation import Located
from soundline.domain.quotes import Span

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def resolve_dataset(dataset: Dataset, documents: DocumentStore) -> dict[str, list[Located]]:
    """Locates every relevant quote in the indexed documents (EVL-002).

    A quote's `source` names a document by its source or by its file name. Quotes match
    regardless of case and whitespace, and resolve to the exact span of the source text.
    Every problem is reported at once, with the closest sentence as a hint.
    """
    sources = documents.sources()
    resolved: dict[str, list[Located]] = {}
    problems: list[str] = []
    for case in dataset.cases:
        located: list[Located] = []
        for relevant in case.relevant:
            matches = [
                s for s in sources if s == relevant.source or _file_name(s) == relevant.source
            ]
            if len(matches) != 1:
                reason = "no indexed document matches" if not matches else "several documents match"
                problems.append(f"case {case.id!r}: {reason} {relevant.source!r}")
                continue
            document = documents.get(matches[0])
            text = document.text if document else ""
            span = _find(relevant.quote, text)
            if span is None:
                problems.append(_not_found(case.id, relevant, text))
            else:
                located.append(Located(matches[0], span))
        resolved[case.id] = located
    if problems:
        raise DatasetError("\n".join(problems))
    return resolved


def _find(quote: str, text: str) -> Span | None:
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
    match = re.search(pattern, text, re.IGNORECASE)
    return Span(match.start(), match.end()) if match else None


def _not_found(case_id: str, relevant: RelevantQuote, text: str) -> str:
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    closest = difflib.get_close_matches(relevant.quote, sentences, n=1, cutoff=0.4)
    hint = f"; closest: {closest[0]!r}" if closest else ""
    return f"case {case_id!r}: {relevant.quote!r} not found in {relevant.source}{hint}"


def _file_name(source: str) -> str:
    return PurePosixPath(source).name
