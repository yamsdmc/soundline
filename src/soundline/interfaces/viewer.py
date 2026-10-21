"""The citation viewer (CLI-007): one self-contained HTML page, no network, no server.

Every piece of document text is escaped: documents are untrusted data (SEC-001).
"""

from collections.abc import Callable
from html import escape

from soundline.domain.answers import Answer, AnswerStatus, Citation
from soundline.interfaces.answer_text import conflict_lines

_CONTEXT_CHARS = 280

_STYLE = """
:root { --bg: #fbfaf8; --fg: #1d1d1f; --muted: #6b6b70; --card: #ffffff; --line: #e4e2dd;
  --mark: #ffe58f; --focus: #2f6fdf; --warn: #b4540a; }
@media (prefers-color-scheme: dark) { :root { --bg: #161618; --fg: #ececee; --muted: #9c9ca3;
  --card: #1f1f22; --line: #333338; --mark: #6b5a12; --focus: #7aa7ff; --warn: #f0a35c; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 32px;
  max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
@media (max-width: 800px) { main { grid-template-columns: 1fr; padding: 16px; } }
h1 { font-size: 1.25rem; margin: 0 0 16px; }
h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted);
  margin: 24px 0 8px; }
.claim { cursor: pointer; border-radius: 4px; padding: 1px 2px; }
.claim:hover, .claim.active { background: color-mix(in srgb, var(--focus) 18%, transparent); }
.refs { color: var(--muted); font-size: .85em; }
.source { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 16px; margin-bottom: 12px; }
.source.active { border-color: var(--focus); box-shadow: 0 0 0 2px var(--focus); }
.where { font-size: .85rem; color: var(--muted); margin-bottom: 6px; }
.excerpt { white-space: pre-wrap; overflow-wrap: anywhere; }
mark { background: var(--mark); color: inherit; border-radius: 2px; }
.badge { font-size: .75rem; color: var(--warn); border: 1px solid currentColor;
  border-radius: 999px; padding: 0 6px; margin-left: 6px; }
.conflict { color: var(--warn); border-left: 3px solid currentColor; padding-left: 10px; }
.removed li { color: var(--muted); text-decoration: line-through; }
"""

_SCRIPT = """
document.querySelectorAll('.claim').forEach(function (claim) {
  claim.addEventListener('click', function () {
    document.querySelectorAll('.active').forEach(function (el) { el.classList.remove('active'); });
    claim.classList.add('active');
    var refs = claim.dataset.refs.split(' ');
    refs.forEach(function (ref) {
      var card = document.getElementById('cite-' + ref);
      if (card) { card.classList.add('active'); }
    });
    var first = document.getElementById('cite-' + refs[0]);
    if (first) { first.scrollIntoView({behavior: 'smooth', block: 'center'}); }
  });
});
"""


def render_viewer(question: str, answer: Answer, document_text: Callable[[str], str]) -> str:
    """`document_text` returns a source's normalized text, which citation spans refer to."""
    numbers = {citation: number for number, citation in enumerate(answer.citations, 1)}
    left = [f"<h1>{escape(question)}</h1>"]
    if answer.status is AnswerStatus.ABSTAINED:
        reason = answer.abstention_message or (
            answer.abstention_reason.value if answer.abstention_reason else "no answer"
        )
        left.append(f"<p>No answer: {escape(reason)}</p>")
    else:
        sentences: list[str] = []
        for claim in answer.claims:
            refs = [numbers[c] for c in claim.citations if c in numbers]
            markers = "".join(f"[{n}]" for n in refs)
            sentences.append(
                f'<span class="claim" data-refs="{" ".join(map(str, refs))}">'
                f'{escape(claim.shown_text)} <span class="refs">{markers}</span></span>'
            )
        left.append(f"<p>{' '.join(sentences)}</p>")
        left += [f'<p class="conflict">{escape(line)}</p>' for line in conflict_lines(answer)]
    if answer.dropped_claims:
        items = "".join(f"<li>{escape(text)}</li>" for text in answer.dropped_claims)
        left.append(
            "<h2>Claims removed: no citation could be verified</h2>"
            f'<ul class="removed">{items}</ul>'
        )
    right = ["<h2>Sources</h2>"]
    right += [_source(n, c, document_text) for c, n in numbers.items()]
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Soundline answer</title><style>{_STYLE}</style></head><body><main>"
        f"<section>{''.join(left)}</section><section>{''.join(right)}</section>"
        f"</main><script>{_SCRIPT}</script></body></html>"
    )


def _source(number: int, citation: Citation, document_text: Callable[[str], str]) -> str:
    text = document_text(citation.source)
    start, end = citation.span.start, citation.span.end
    before = text[max(0, start - _CONTEXT_CHARS) : start]
    after = text[end : end + _CONTEXT_CHARS]
    where = escape(citation.source.rsplit("/", 1)[-1])
    if citation.section_path:
        where += " &middot; " + " &rsaquo; ".join(escape(part) for part in citation.section_path)
    badge = '<span class="badge">approximate</span>' if citation.approximate else ""
    return (
        f'<div class="source" id="cite-{number}"><div class="where">[{number}] {where}{badge}'
        f'</div><div class="excerpt">{"…" if start > _CONTEXT_CHARS else ""}{escape(before)}'
        f"<mark>{escape(text[start:end])}</mark>{escape(after)}"
        f"{'…' if end + _CONTEXT_CHARS < len(text) else ''}</div></div>"
    )
