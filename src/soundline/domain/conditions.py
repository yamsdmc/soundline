"""Conditions of a section (GEN-094, GEN-095): what a claim must keep from where it is quoted.

"Logement vide" is a condition when "Logement meublé" sits next to it: a rule quoted under one
of them holds for that case only.
"""

import re
import unicodedata
from collections.abc import Sequence

from soundline.domain.answers import Claim
from soundline.domain.chunks import Chunk


def missing_conditions(claim: Claim, evidence: Sequence[Chunk]) -> tuple[str, ...]:
    """The headings every citation of the claim lies under, that have a sibling section in the
    same document's evidence and that the claim does not name."""
    sources = {citation.source for citation in claim.citations}
    if len(sources) != 1:
        return ()
    source = sources.pop()
    shared = _common_prefix([citation.section_path for citation in claim.citations])
    said = _words(claim.text)
    missing: list[str] = []
    for depth, heading in enumerate(shared):
        siblings = {
            chunk.section_path[depth]
            for chunk in evidence
            if chunk.source == source
            and len(chunk.section_path) > depth
            and chunk.section_path[:depth] == shared[:depth]
            and chunk.section_path[depth] != heading
        }
        if not siblings:
            continue
        distinguishing = _words(heading) - set().union(*(_words(s) for s in siblings))
        if distinguishing and not distinguishing & said:
            missing.append(heading)
    return tuple(missing)


def _common_prefix(paths: Sequence[tuple[str, ...]]) -> tuple[str, ...]:
    prefix = paths[0] if paths else ()
    for path in paths[1:]:
        length = 0
        while length < min(len(prefix), len(path)) and prefix[length] == path[length]:
            length += 1
        prefix = prefix[:length]
    return prefix


def _words(text: str) -> set[str]:
    """Case and accents ignored."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in folded if not unicodedata.combining(c))
    return set(re.findall(r"\w+", plain))
