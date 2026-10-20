# 0007 — Structured claims with verified quote citations

- Status: Accepted
- Date: 2026-10-20

## Context

Typical RAG citations are markers (`[1]`) that the model places at its own discretion. Nothing checks that the cited passage supports the sentence, or even that the marker refers to a real passage. Users cannot verify claims without re-reading sources.

## Decision

- The model returns **structured output**: a list of claims, each with citations made of an evidence ID and a **verbatim quote**.
- Soundline **verifies** each quote against the cited evidence (exact → normalized → fuzzy), resolves it to an exact span and location, and **drops** unverifiable citations and unsupported claims, with explicit `PARTIAL` / `ABSTAINED` statuses.
- When fuzzy matching is used, the displayed quote is the **source text**, never the model's version, and only if the **critical tokens** (numbers, dates, amounts, identifiers) agree exactly (GEN-037). The citation is flagged `approximate`.
- There is no exemption for "non-factual" claims: every claim needs a verified citation (GEN-033).
- **Provider-native citations** (e.g. Anthropic's Citations API, which returns cited text with character offsets) are supported as an input mode (GEN-022), and go through the same verification.

## Consequences

- Citations shown to users are guaranteed to exist in the source (INV-GEN-1), with agreeing critical tokens (INV-GEN-5). They are guaranteed to be *present*, not to *entail* the claim. Entailment is measured by the faithfulness judge (EVL-041), and may later be checked by an NLI stage.
- Soundline's distinctive value is **not** that citations exist (some providers and models now produce precise citations natively). It is that verification is **provider-independent**, applies uniformly to local and hosted models, and that its effect is **measured** (EVL-092).
- Requires models with reliable structured output. Older or smaller local models may produce more invalid outputs; this is measured by `citation_validity`.
- Answers may be shorter or more often partial. This trade-off follows principle 1 (correctness over fluency).

## Alternatives considered

- **Post-hoc attribution** (generate freely, then match sentences to passages by similarity): works with any model, but attributions are guesses, not commitments.
- **Free text with markers + validation of marker IDs only**: cheap, but does not prove anything about content.
- **Relying on provider-native citations only** (Anthropic Citations API; models trained to cite verbatim, such as Pleias-RAG): precise and cheaper in output tokens, but ties the guarantee to specific providers and models, and gives no uniform check across them. Kept as an input mode, not as the trust mechanism.
- **Fuzzy matching on similarity alone**: rejected, because a one-digit change ("5 %" → "6 %") keeps similarity above any useful threshold while inverting meaning.
