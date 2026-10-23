"""An answer as plain text, the same in every text interface (CLI, MCP)."""

from pathlib import PurePosixPath

from soundline.domain.answers import Answer, AnswerStatus


def answer_text(answer: Answer) -> str:
    if answer.status is AnswerStatus.ABSTAINED:
        reason = answer.abstention_reason.value if answer.abstention_reason else "unknown"
        return f"No answer ({reason}). {answer.abstention_message or ''}".rstrip()
    lines = [answer.text, *conflict_lines(answer), ""]
    for number, citation in enumerate(answer.citations, 1):
        where = " > ".join(citation.section_path)
        page = f", p. {citation.page}" if citation.page is not None else ""
        label = PurePosixPath(citation.source).name + page + (f", {where}" if where else "")
        marker = " (approximate)" if citation.approximate else ""
        lines.append(f'[{number}] {label}: "{citation.quote}"{marker}')  # GEN-042
    if answer.dropped_claims:
        lines += ["", f"{answer.status.value}: unsupported claims were removed:"]
        lines += [f"  - {claim}" for claim in answer.dropped_claims]
    return "\n".join(lines)


def conflict_lines(answer: Answer) -> list[str]:
    """One line per pair of disagreeing sources, by citation number (GEN-092)."""
    return [
        f"Sources disagree on {conflict.about}: "
        + " ".join(f"[{answer.citations.index(c) + 1}]" for c in conflict.citations)
        for conflict in answer.conflicts
    ]
