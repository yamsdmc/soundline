"""Language of a question, from its function words (GEN-015).

Questions are short, so a statistical detector is unreliable on them; function words are
enough to pick between the languages we name, and `None` says "not enough signal".
"""

import re

_FUNCTION_WORDS: dict[str, str] = {
    "en": "the is are was when what which who how does do of to and in for on with can must"
    " should my your",
    "fr": "le la les des du une est dans quel quelle quels quelles quand comment pourquoi doit"
    " il elle je mon ma mes pour sur avec qui au aux et ou",
    "es": "el los las del es cuándo cuando qué cómo dónde se por para una con mi su y al",
    "de": "der die das den dem ist wann wie was wer muss kann und ein eine mit für von zu nicht",
    "it": "il lo gli della che è quando come perché deve una con sono dove cosa quale",
    "pt": "o os as do da dos em não quando como tem uma um é ao na no",
}
_NAMES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
}
_WORD = re.compile(r"[^\W\d_]+")
_VOCABULARIES = {code: frozenset(words.split()) for code, words in _FUNCTION_WORDS.items()}


def detect_language(text: str) -> str | None:
    """An ISO 639-1 code, or None when no language clearly leads."""
    words = _WORD.findall(text.lower())
    scores = sorted(
        (
            (sum(word in vocabulary for word in words), code)
            for code, vocabulary in _VOCABULARIES.items()
        ),
        reverse=True,
    )
    (best, code), (second, _) = scores[0], scores[1]
    return code if best > second else None


def language_name(code: str) -> str:
    return _NAMES[code]
