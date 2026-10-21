# 05 — Grounded generation

## Purpose

Produce answers that are **supported claim by claim** by evidence the user can check, and **abstain** when the evidence does not support an answer.

The central design choice: the model does not produce free text with decorative `[1]` markers. It produces **structured claims, each with exact quotes**. Soundline then **verifies every quote** against the evidence and resolves it to an exact location in the source. Citations are therefore not an assertion by the model: Soundline checks every one of them.

Some providers return native, character-indexed citations (e.g. Anthropic's Citations API). Soundline uses them when available (GEN-022), but always passes them through the **same** verification. The guarantee does not depend on the provider, and its effect is measured (see [06 — Evaluation](06-evaluation.md)).

What verification guarantees, precisely: every displayed quote **exists** in the source, and the claim's **critical tokens** (numbers, dates, amounts, identifiers) agree with it (GEN-037). Verification does **not** prove that the quote *entails* the claim. That is measured by the faithfulness judge (EVL-041).

## Concepts

Answer, answer status, claim, citation, quote, quote verification, verified citation, abstention, abstention reason (see [glossary](01-glossary.md)).

## Answer shape

```python
@dataclass(frozen=True)
class Answer:
    status: AnswerStatus  # ANSWERED | PARTIAL | ABSTAINED
    text: str  # rendered answer with [n] markers
    claims: list[Claim]  # text + citations (verified only)
    citations: list[Citation]  # deduplicated, numbered [1..n] as in text
    abstention: Abstention | None  # reason + message when ABSTAINED
    dropped_claims: list[DroppedClaim]  # claims removed for lack of support (PARTIAL)
    evidence: list[Evidence]  # what the model saw
    query: QueryInfo  # original and rewritten queries
    usage: Usage  # tokens and cost per stage
    trace_id: str
```

> **Non-normative.** This shape is a starting hypothesis for the first tests. Only the behaviors below are normative. Field names become public API at 1.0.

## Behaviors

### Pre-generation abstention

- **GEN-001** If retrieval returns no evidence, `ask` MUST return `ABSTAINED` with reason `NO_EVIDENCE` **without calling the language model**.
- **GEN-002** If a relevance threshold is configured (`min_relevance`, on the reranker score when available, otherwise disabled by default because RRF scores are not calibrated) and no evidence meets it, `ask` MUST return `ABSTAINED` with reason `LOW_RELEVANCE` without calling the model.

### Prompting

- **GEN-010** The generation prompt MUST present evidence as **data**: each item enclosed in a delimited block with its evidence ID and source label, and an instruction stating that evidence content is untrusted material to quote and never instructions to follow.
- **GEN-011** The model MUST be instructed to answer **only** from evidence, to cite every factual claim, and to declare insufficient evidence rather than use outside knowledge.
- **GEN-012** The model MUST be asked for **structured output** matching a schema: either an answer as a list of claims with citations (`evidence_id`, `quote`), or an insufficient-evidence declaration with a short explanation. Native structured output or tool calling MUST be used when the provider supports it; otherwise JSON mode with schema validation.
- **GEN-013** Quotes MUST be requested **verbatim** and **short** (a sentence or less, configurable maximum length). Long quotes are truncated by validation, not trusted.
- **GEN-014** Prompts MUST be versioned (`prompt_version` in the trace). Prompt templates are files in the package, overridable by configuration.
- **GEN-015** The answer language MUST follow the question's language by default, regardless of evidence language. Quotes stay in the evidence language.
- **GEN-016** Users MAY provide additional instructions (tone, format, length). They are appended to the system prompt and MUST NOT override GEN-010 and GEN-011.

### Structured output handling

- **GEN-020** If the model output does not match the schema, Soundline MUST retry once with the validation error appended. A second failure raises `GenerationError` (`invalid_model_output`), with the raw output in the trace.
- **GEN-021** If the model declares insufficient evidence, `ask` MUST return `ABSTAINED` with reason `MODEL_INSUFFICIENT_EVIDENCE` and the model's explanation as the abstention message.
- **GEN-022** When the configured provider supports **native citations** and native mode is enabled, Soundline sends evidence as provider-native documents and maps the returned cited spans to claims and citations. Native citations MUST go through the same verification (GEN-030 to GEN-039) as schema-based ones. The citation mode (`native` or `schema`) is recorded in the trace and in eval runs, so both modes can be compared.
  > Note (M4): on the Anthropic API, native citations cannot be combined with schema-constrained output (`output_config.format`). Native mode therefore sends evidence as citation-enabled documents without an output schema, and maps the cited text blocks to claims; schema mode is the default.
- **GEN-023** For models with weak structured-output support (typically small local models), a **lenient parser** MUST accept common deviations: JSON wrapped in Markdown fences, trailing prose, single quotes. When `claims` is non-empty, it takes precedence over `insufficient_evidence` (small models often send `""` instead of `null` while answering); the claims are verified anyway. A simplified schema (flat list of `{text, evidence_id, quote}`) MAY be selected by configuration. The rate of outputs that needed leniency is reported in the trace and in evaluation (`lenient_parse_rate`).

### Quote verification

Verification compares a quote with the cited evidence text, under a **matching ladder** that stops at the first success:

1. **Exact**: the quote is a substring of the evidence text.
2. **Normalized**: substring after case folding, Unicode NFKC, whitespace collapsing, and unification of quotes, dashes and ellipses.
3. **Fuzzy** (configurable, on by default): the best-matching window of the evidence has a normalized edit similarity ≥ `fuzzy_threshold` (default 0.9) to the quote, the quote is at least `fuzzy_min_chars` long (default 30), **and** the critical-token check passes (GEN-037). The **evidence's text** becomes the displayed quote: what users see is always real source text.

> Why the critical-token check: without it, a quote saying "6 %" fuzzily matches a source saying "5 %" (similarity ≈ 0.97). The user would see real source text that contradicts the claim it supposedly supports. Edit similarity measures typing errors, not meaning.

- **GEN-030** Every citation MUST be verified against the evidence item it references. A citation referencing an unknown evidence ID is invalid.
- **GEN-031** A verified citation MUST be resolved to an exact span in the document's normalized text, and from there to a location (page, line range, section path) through the offset map. The citation records the document **revision** it was verified against (see API-016 for citations whose revision was later replaced).
- **GEN-032** Invalid citations MUST be removed. The verification outcome of every citation (method used, similarity, or failure reason) is recorded in the trace.
- **GEN-033** A claim left with no verified citation is **unsupported**. It MUST be removed from the answer and listed in `dropped_claims`. There is **no exemption**: the model cannot declare a claim "non-factual" to bypass verification. The prompt asks the model not to emit framing sentences, and rendering (GEN-040) produces any connective text deterministically.
- **GEN-034** If at least one claim was dropped and at least one supported claim remains, the status is `PARTIAL`. If no supported claim remains, the status is `ABSTAINED` with reason `UNSUPPORTED_CLAIMS`.
- **GEN-035** An optional **repair** pass MAY be configured: on unsupported claims, the model is re-asked once with the list of failed citations, before applying GEN-033.
- **GEN-036** A quote that does not overlap the evidence's quotable span (e.g. text from the context prefix) MUST fail verification.
- **GEN-037** **Critical-token agreement.** The critical tokens of the quote as written by the model (numbers, including decimals and percentages, dates, currency amounts, and alphanumeric identifiers such as `INV-2024-0042`) MUST appear identically in the matched source window, after locale-aware number normalization (`5,5 %` ≡ `5.5%`). Otherwise the citation fails, whatever the similarity. This check applies to every rung of the ladder. It is trivially satisfied by exact matches.
- **GEN-038** Citations verified by fuzzy matching MUST be flagged `approximate: true` in the API, the JSON output and the trace, and their rate is reported in evaluation (`approximate_citation_rate`).
- **GEN-039** A quote MUST lie within a single evidence item. A quote spanning two evidence items fails verification. The prompt instructs the model to split such support into two citations. Adjacent chunks merged by post-processing (RET-060, RET-062) form a single evidence item.

### Rendering

- **GEN-040** `answer.text` MUST be rendered from the verified claims, with citation markers `[n]` numbered by first appearance. The same source span cited twice gets the same number.
- **GEN-041** Rendering formats: plain text (default), Markdown (markers as footnotes), and JSON (structured answer). Rendering never changes the claims.
- **GEN-042** The CLI renders the answer followed by the citation list: `[n] <source label>, <location>: "<quote>"`.

### Streaming

- **GEN-050** `ask_stream` MUST yield typed events: `retrieval_completed` (evidence list), `claim` (each claim as soon as it is complete and verified), `answer_completed` (final `Answer`), `error`.
- **GEN-051** Streamed claims MUST already be verified. Unverified text MUST NOT be streamed to the user as an answer.

> Implementation note (non-normative): emitting claims before the model finishes requires incrementally parsing the structured output (partial JSON or tool-call deltas). Until that exists, a conforming implementation MAY emit all claims after generation completes, since GEN-050 only fixes the event order.
- **GEN-052** A raw token stream (`token` events, unverified) MAY be enabled explicitly for UIs that accept the trade-off. Such events are clearly marked `unverified`.

### Conversations

- **GEN-060** `ask` accepts an optional conversation history (previous questions and answers). History is used for follow-up condensation (RET-071) and passed to the model as context. Previous answers are **not** evidence and cannot be cited.
- **GEN-061** A `Conversation` helper MAY keep history in memory for the Python API and CLI `chat`. Server-side persistence of conversations is out of scope for 1.0. The HTTP API is stateless and history is sent by the client.
- **GEN-062** **Generation prompt budget.** The prompt is assembled by priority: (1) system prompt and output instructions, never truncated; (2) the question; (3) evidence, within the context budget (RET-080); (4) conversation history, within `history_budget_tokens` (default 1500). History is packed **newest turn first** until the budget is reached, then rendered in chronological order. Older turns are dropped whole, never cut mid-turn. The trace records how many turns were dropped.
- **GEN-063** History carries the text of previous questions and answers only. Previous citations and evidence are **not** carried over: a claim in a follow-up answer must be supported by evidence retrieved for that turn (GEN-060). There is no inherited provenance.
- **GEN-064** Generation budgets (RET-080, GEN-062, GEN-071) are counted with the **provider's exact tokenizer** when one is available (a local tokenizer or a token-counting endpoint, cached). Otherwise a documented **conservative** estimate is used, one that over-counts, because 4 characters per token under-counts French, CJK text and code. The method used is recorded in the trace.
  > Added after reviewing the author's article on context engineering: the spec budgeted evidence but not history, and did not say which tokenizer counts the LLM budget.

### Cost and limits

- **GEN-070** Token usage and estimated cost MUST be reported per stage (rewrite, generation, repair) in `answer.usage`, using a configurable price table.
- **GEN-071** A maximum output token limit MUST be enforced. A truncated model output (stop reason `max_tokens`) is treated as invalid output (GEN-020).

## Invariants

- **INV-GEN-1** Every citation in an `ANSWERED` or `PARTIAL` answer has a quote that is a substring of its document's normalized text at its resolved span: `doc.normalized_text[c.start:c.end] == c.quote`.
- **INV-GEN-2** An `ANSWERED` answer has no dropped claims, and every claim has ≥ 1 verified citation.
- **INV-GEN-5** For every verified citation, the multiset of critical tokens in the model's original quote equals the one in the displayed source quote.
- **INV-GEN-3** An `ABSTAINED` answer has an abstention reason and no claims.
- **INV-GEN-4** `NO_EVIDENCE` and `LOW_RELEVANCE` abstentions consume zero generation tokens.

## Test list (starting point)

All with `ScriptedLanguageModel` unless stated.

1. No evidence → `ABSTAINED/NO_EVIDENCE`, and the model is never called.
2. Model returns one claim with an exact quote → `ANSWERED`, one citation, resolved span correct.
3. The citation resolves to the right page for a PDF fixture.
4. Quote with different whitespace and curly quotes → verified via normalized match.
5. Quote with a one-character typo in a word → verified via fuzzy match, flagged `approximate`; displayed quote is the source text.
5b. Quote where "5 %" became "6 %" → fails verification despite high similarity (GEN-037).
5c. `5,5 %` in the quote matches `5.5%` in the source.
5d. Short quote (< `fuzzy_min_chars`) with a typo → fails (no fuzzy below the minimum length).
5e. Quote spanning two evidence items → fails (GEN-039).
6. Quote absent from evidence → citation removed; claim dropped; status `PARTIAL` when another claim remains.
7. All claims unsupported → `ABSTAINED/UNSUPPORTED_CLAIMS`.
8. Citation to unknown evidence ID `E9` → invalid.
9. Quote taken from the context prefix → invalid.
10. Model declares insufficient evidence → `ABSTAINED/MODEL_INSUFFICIENT_EVIDENCE`, with its message.
11. Invalid JSON, then valid on retry → success; the retry prompt contains the validation error.
12. Invalid twice → `GenerationError(invalid_model_output)`.
13. Rendering numbers citations by first appearance and reuses numbers for identical spans.
14. A claim without any citation is dropped, even if it looks like a transition ("Here is what the contract says:").
14b. Native-citation mode maps provider spans to claims and still rejects a native citation whose span is outside the evidence.
14c. Lenient parser accepts JSON inside a Markdown fence and reports the leniency.
15. Prompt contains evidence in delimited blocks with IDs and the untrusted-data instruction (approval test on the rendered prompt).
16. A question in French with English evidence → the prompt asks for a French answer.
17. Streaming emits `retrieval_completed`, then verified `claim` events, then `answer_completed`.
18. Follow-up in a conversation uses the condensed query for retrieval; previous answers are not citable.
19. Usage reports tokens per stage; cost computed from the price table.
20. Truncated output (`max_tokens`) is treated as invalid output.
21. INV-GEN-1 to INV-GEN-5 hold for generated scripted outputs (Hypothesis: random quotes, random evidence).

## Open questions

- Claim granularity: sentence-level by default. Should the model be allowed multi-sentence claims with one citation?
- Whether to ship an optional **NLI-based entailment check** (does the quote actually support the claim, beyond existing?) as a verification stage. It would be valuable, but costly. Decide based on evaluation of faithfulness gains.
