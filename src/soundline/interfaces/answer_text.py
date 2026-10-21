"""An answer as plain text, the same in every text interface (CLI, MCP)."""

from pathlib import PurePosixPath

from soundline.domain.answers import Answer, AnswerStatus


def answer_text(answer: Answer) -> str:
    if answer.status is AnswerStatus.ABSTAINED:
        reason = answer.abstention_reason.value if answer.abstention_reason else "unknown"
        return f"No answer ({reason}). {answer.abstention_message or ''}".rstrip()
    lines = [answer.text, ""]
    for number, citation in enumerate(answer.citations, 1):
        where = " > ".join(citation.section_path)
        label = PurePosixPath(citation.source).name + (f", {where}" if where else "")
        marker = " (approximate)" if citation.approximate else ""
        lines.append(f'[{number}] {label}: "{citation.quote}"{marker}')  # GEN-042
    if answer.dropped_claims:
        lines += ["", f"{answer.status.value}: unsupported claims were removed:"]
        lines += [f"  - {claim}" for claim in answer.dropped_claims]
    return "\n".join(lines)
