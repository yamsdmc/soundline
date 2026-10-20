# 03 — Ingestion

## Purpose

Turn sources into searchable chunks **deterministically**, **incrementally**, and with **full provenance**, so that every retrieved passage can be traced back to an exact location in an exact revision of its source.

Ingestion quality bounds everything downstream. A table shredded during parsing cannot be repaired by a better model.

## Concepts

Source, document, revision, parsed document, element, normalized text, offset map, location, section path, chunk, context prefix, embedding, pipeline fingerprint (see [glossary](01-glossary.md)).

## Pipeline stages

1. **Discover**: expand inputs (files, directories, globs, URLs) into source URIs.
2. **Read**: fetch raw bytes and compute the revision (SHA-256).
3. **Skip unchanged**: stop if the document already exists at this revision with the current fingerprint.
4. **Parse**: bytes → elements + normalized text + offset map.
5. **Chunk**: normalized text + elements → chunks.
6. **Enrich** (optional): chunk + document → context prefix.
7. **Embed**: (context prefix + chunk text) → vector.
8. **Commit**: atomically replace the document's previous chunks.

## Behaviors

### Discovery

- **ING-001** Given a file path, Soundline ingests that file.
- **ING-002** Given a directory, Soundline ingests all supported files recursively. Hidden files and directories (dot-prefixed) are skipped by default.
- **ING-003** Include and exclude glob patterns MAY be given. A `.soundlineignore` file (gitignore syntax) in a directory applies to that directory tree.
- **ING-004** Unsupported media types are skipped and reported as `skipped: unsupported_media_type`. They are not errors.
- **ING-005** Media type is detected from content sniffing first, then file extension. A mismatch is reported as a warning.
- **ING-006** Symbolic links are not followed by default (prevents cycles and escaping the ingested tree).

### Identity and idempotency

- **ING-007** Re-ingesting a source whose bytes are unchanged MUST be a no-op: no parse, no embedding call, no write. It is reported as `unchanged`. (A changed pipeline cannot reach this point: STO-010 rejects the ingestion first.)
- **ING-008** The document ID MUST be derived deterministically from `(corpus, normalized source URI)`. The same file ingested twice keeps the same document ID.
- **ING-009** Re-ingesting a source whose bytes changed MUST replace all of the document's chunks atomically. Concurrent searches see either the old revision or the new one, never a mix or nothing.
- **ING-010** Chunk IDs MUST be deterministic: derived from `(document ID, revision, chunk span, pipeline fingerprint)`. Same input and configuration → same IDs.
- **ING-011** `sync` reconciles a corpus with a set of inputs: new sources are added, changed sources are updated, and sources no longer present are **deleted**. Plain `ingest` never deletes.
- **ING-012** Two different source URIs with identical bytes are two documents. Deduplication by content is reported as an informational notice, not enforced.

### Parsing

- **ING-020** Every parser MUST produce normalized text: Unicode NFC, line endings normalized to `\n`, runs of horizontal whitespace collapsed to one space, at most two consecutive newlines, and no leading or trailing whitespace on the document.
- **ING-021** Every parser MUST produce an offset map such that any span of normalized text can be resolved to a location: page (PDF, DOCX when available), line range (text, Markdown, code), and section path.
- **ING-022** Markdown and HTML parsers MUST recognize headings (with level), paragraphs, lists, tables, code blocks and block quotes as elements.
- **ING-023** HTML parsing MUST drop scripts, styles, navigation and other non-content markup. Visible text is preserved.
- **ING-024** Tables MUST be rendered in normalized text as Markdown tables (header row, separator, body rows), so that their structure survives into chunks and prompts.
- **ING-025** The PDF parser MUST extract the text layer page by page and preserve page boundaries in the offset map. On the committed single-column fixtures, the normalized text MUST equal the fixture's expected reading-order text (golden files). Multi-column and complex layouts are out of scope for the built-in parser and are delegated to the optional Docling parser.
- **ING-026** A PDF without an extractable text layer (scanned) MUST produce the warning `no_text_layer`, with a hint about the OCR-capable parser. It MUST NOT create an empty document silently.
- **ING-027** Repeated page headers and footers in PDFs (text recurring at the same position on most pages) SHOULD be detected and excluded from normalized text.
- **ING-028** Parsers MUST extract available document metadata (title, author, creation date, language when detectable) into reserved metadata keys prefixed `sl.` (e.g. `sl.title`).
- **ING-029** Users MAY attach metadata at ingestion time (`--meta key=value`, or a sidecar file `<file>.meta.json`). User metadata MUST NOT use the `sl.` prefix.
- **ING-030** Parser failures on one source MUST NOT abort ingestion of other sources. Failures are collected and reported per source with a stable error code.

### Chunking

The default chunker is **structure-aware**. Its observable properties are ING-040 to ING-049 and the invariants below.

> **Non-normative starting hypothesis** for the algorithm. TDD may arrive at a different one, provided the behaviors hold:
>
> 1. Split along the element tree: sections (by heading), then elements.
> 2. Merge adjacent small elements of the same section until the target size is reached.
> 3. Split elements larger than the maximum size at the most semantic boundary available: paragraph, sentence, then word. Never split inside a word.
> 4. Apply the overlap between consecutive chunks of the same section.

- **ING-040** Every chunk MUST be a contiguous span `[start, end)` of the document's normalized text. Chunk text MUST equal `normalized_text[start:end]`.
- **ING-041** Every chunk MUST contain at most `max_tokens` tokens (default 384) as counted by the configured tokenizer, **and** the text actually sent to the embedder (query/passage prefix + context prefix + chunk text) MUST fit within `Embedder.max_input_tokens` as counted by `Embedder.count_tokens`. When the second limit is the binding one, the chunker uses it, and the effective limit is reported in the manifest.
- **ING-042** Chunks SHOULD contain at least `min_tokens` tokens (default 64), except when a section or the document is shorter.
- **ING-043** Chunks MUST NOT cross a heading boundary of level ≤ `section_split_level` (default 2). A chunk belongs to exactly one section path.
- **ING-044** A table that fits within `max_tokens` MUST NOT be split. A larger table MUST be split between rows, and each part MUST be indexed with the table's header row repeated in its **context prefix**. The header is not duplicated in the chunk span.
- **ING-045** A code block that fits within `max_tokens` MUST NOT be split. A larger one is split on blank lines, then on line boundaries.
- **ING-046** Consecutive chunks within a section MAY overlap by up to `overlap_tokens` (default 64). Overlap MUST align to sentence boundaries when possible.
- **ING-047** Every chunk MUST carry its section path, its location (page range / line range) and its ordinal position in the document.
- **ING-048** Alternative chunking strategies (fixed-size token windows, sentence windows, one chunk per element) MUST be selectable by configuration, for experimentation.
- **ING-049** Chunking MUST be deterministic and independent of the embedder.

### Contextual enrichment (optional)

- **ING-060** When enabled, each chunk receives a context prefix generated by a language model from the document and the chunk (default prompt: 50–100 tokens situating the chunk within the document).
- **ING-061** By default, the context prefix MUST be prepended to the chunk text for **embedding and lexical indexing**. It MUST NOT be part of the chunk's quotable span.
- **ING-062** Enrichment calls MUST be cached by `(document revision, chunk span, model ID, prompt version)`. Re-ingesting unchanged content costs zero model calls.
- **ING-063** For long documents, the document context sent to the enrichment model MUST be truncated to a configurable budget centered on the chunk, and SHOULD use provider prompt caching when available.
- **ING-064** Section paths MUST be included in the context prefix even when LLM enrichment is disabled (cheap structural context: `"Lease agreement > 3. Payment > 3.2 Late fees"`).
- **ING-065** An enrichment failure on a chunk MUST degrade gracefully: the chunk is indexed with the structural prefix only, and a warning is reported.
- **ING-066** Before running enrichment, `ingest --estimate` (and the confirmation prompt shown when the estimate exceeds `enrichment.confirm_above_usd`) reports the number of model calls, input tokens and estimated cost. Enrichment cost grows with document length × chunk count, so long documents are the dominant cost.
- **ING-067** Enrichment is nondeterministic. Chunk IDs and spans (ING-010, INV-ING-5) MUST NOT depend on enrichment output. Context prefixes are reproducible only through the cache (ING-062), and the manifest records whether a corpus was enriched.

### Embedding

- **ING-070** Texts MUST be embedded in batches of configurable size, with bounded concurrency.
- **ING-071** Retryable provider errors MUST be retried with exponential backoff and jitter. After exhaustion, the affected document fails with `embedding_failed`, and other documents continue.
- **ING-072** Texts exceeding the embedder's input limit MUST NOT be silently truncated by the provider. ING-041 guarantees this for chunk text plus prefixes, measured with the embedder's own tokenizer. If a context prefix makes an embedding input too long, the **prefix** is truncated (never the chunk), and a warning is reported.
- **ING-073** Every stored vector MUST be tagged with the embedder model ID and dimension, through the manifest (see STO chapter).

### Reporting and progress

- **ING-080** Ingestion returns a report with, per source: status (`added`, `updated`, `unchanged`, `deleted`, `skipped`, `failed`), document ID, revision, chunk count, warnings, and error code if failed. Totals include duration, tokens embedded and model costs where known.
- **ING-081** The CLI displays progress (sources processed / total, current stage) and a summary. `--json` emits the report as JSON.
- **ING-082** Ingestion is **resumable**: interrupting it leaves every document either fully committed at its new revision or untouched. Re-running continues where it stopped, via idempotency.
- **ING-083** Limits (max file size, max pages, max total chunks per document) MUST be configurable. Exceeding them fails the source with a clear code (`source_too_large`…).

## Invariants (property-based test candidates)

- **INV-ING-1 (span fidelity)** For every chunk `c` of document `d`: `d.normalized_text[c.start:c.end] == c.text`.
- **INV-ING-2 (coverage)** The union of chunk spans covers every non-whitespace character of the normalized text, except content intentionally excluded (detected headers and footers are excluded before normalization, so normalized text contains none).
- **INV-ING-3 (ordering)** Chunk spans are ordered by `start`. Overlap exists only between consecutive chunks of the same section, and never exceeds `overlap_tokens`.
- **INV-ING-4 (size)** `tokens(c.text) ≤ max_tokens` for every chunk.
- **INV-ING-5 (determinism)** `chunk(x) == chunk(x)` across processes. IDs are stable. Cross-platform stability is checked by golden chunk files compared in the CI matrix (Linux, macOS, Windows).
- **INV-ING-6 (normalization idempotency)** `normalize(normalize(t)) == normalize(t)`.
- **INV-ING-7 (location monotonicity)** For PDFs, chunk page ranges are non-decreasing with chunk order.

## Test list (starting point)

Ordered roughly from simplest to hardest. The first item is part of the walking skeleton.

1. A one-line `.txt` file yields one document with one chunk equal to its text.
2. Ingesting the same file twice reports `unchanged` the second time and makes no embedder call.
3. Modifying the file then re-ingesting reports `updated`; old chunks are gone and new ones are searchable.
4. A text longer than `max_tokens` yields several chunks, each within the limit.
4b. With an embedder whose tokenizer counts 3× more tokens than the configured tokenizer (fake), chunks are sized to the embedder's limit.
4c. An over-long context prefix is truncated, and the chunk is not.
5. Splitting never happens inside a word.
6. Splitting prefers sentence boundaries over word boundaries when both are available.
7. Normalization collapses whitespace and normalizes line endings; offsets refer to normalized text.
8. Markdown headings produce section paths on chunks.
9. A chunk never crosses a level-2 heading.
10. A small Markdown table stays in one chunk.
11. A large table is split between rows, with the header row in each part's context prefix.
12. A small fenced code block stays in one chunk.
13. HTML scripts and navigation are excluded from normalized text.
14. Directory ingestion skips hidden files and unsupported media types, and reports them.
15. `.soundlineignore` excludes matching files.
16. A parser failure on one file does not prevent other files from being ingested.
17. `sync` deletes documents whose sources disappeared; `ingest` does not.
18. PDF chunks carry correct page ranges (fixture: 3-page PDF with known text per page).
19. A scanned PDF yields `no_text_layer` and no empty document.
20. Repeated PDF headers and footers are excluded.
21. User metadata from `--meta` and sidecar files is attached and inherited by chunks.
22. The `sl.` prefix is rejected in user metadata.
23. Enrichment prefixes are indexed but not quotable.
24. Enrichment results are cached: re-ingesting after deleting the index makes zero LLM calls.
25. Enrichment failure falls back to the structural prefix with a warning.
26. A retryable embedding error is retried and succeeds.
27. An exhausted embedding retry fails only the affected document.
28. Interrupting ingestion mid-way leaves no partially committed document (simulated crash in the fake store).
29. Properties INV-ING-1 to INV-ING-6 hold for arbitrary generated documents (Hypothesis).

## Open questions

- Sentence segmentation: a rule-based segmenter (fast, language-agnostic heuristics) or `pysbd`? Decide with multilingual fixtures (FR, EN, DE, ZH).
- Should semantic chunking (splitting where embedding similarity drops) be offered? Only if evaluation shows a gain over structural chunking on the benchmark suite.
- Late chunking for long-context embedders: track as an experiment, not a 1.0 feature.
