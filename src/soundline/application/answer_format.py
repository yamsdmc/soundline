"""The structured answer every language model adapter asks for (GEN-012)."""

from soundline.application.ports import OutputFormat

# The answer contract of docs/spec/05-generation.md as a strict JSON schema: both fields are
# always present, `insufficient_evidence` is null when the model answers.
ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["evidence_id", "quote"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text", "citations"],
                "additionalProperties": False,
            },
        },
        "insufficient_evidence": {"type": ["string", "null"]},
    },
    "required": ["claims", "insufficient_evidence"],
    "additionalProperties": False,
}

ANSWER_FORMAT = OutputFormat("grounded_answer", ANSWER_SCHEMA)

# A follow-up rewritten into a standalone search query (RET-071).
CONDENSE_FORMAT = OutputFormat(
    "standalone_query",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
)
