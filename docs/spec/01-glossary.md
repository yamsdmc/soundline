# 01 — Glossary (ubiquitous language)

These terms are used consistently in the specification, the code, the tests and the documentation. If code needs a concept not listed here, add it here first.

## Corpus and documents

**Corpus**
: A named collection of documents that are searched together. A corpus is the unit of isolation: a query never returns content from another corpus. Default name: `default`.

**Source**
: Where a document comes from, identified by a **source URI** (`file:///abs/path/lease.pdf`, `https://…`, `upload://<id>`). Within a corpus, a source URI identifies at most one live document.

**Document**
: An ingested source. It has a stable **document ID** (derived from corpus + source URI), a **revision** (content hash of the raw bytes), a media type, and **metadata** (key/value pairs, user-supplied or extracted).

**Revision**
: The content hash (SHA-256) of a document's raw bytes. A changed file produces a new revision. Unchanged bytes keep the same revision.

**Metadata**
: Typed key/value attributes attached to a document and inherited by its chunks: string, number, boolean, date, or list of strings. Used for filtering.

## Parsing

**Parsed document**
: The output of a parser: an ordered sequence of **elements** plus the document's **normalized text**.

**Element**
: A structural unit of a parsed document: `heading` (with level), `paragraph`, `list_item`, `table`, `code`, `quote`, `caption`, `page_break`. Each element knows its span in the normalized text and its **location** in the original.

**Normalized text**
: The document's text after Unicode NFC normalization and whitespace canonicalization. All character offsets in Soundline refer to the normalized text.

**Offset**
: A position in normalized text, counted in **Unicode code points** (Python `str` indexing). Outputs consumed by other languages (HTTP, MCP, JSON) also carry **UTF-16 code unit** offsets (`utf16_start`, `utf16_end`) so that JavaScript clients can highlight spans correctly when text contains characters outside the Basic Multilingual Plane (e.g. emoji).

**Offset map**
: A mapping from normalized-text offsets back to locations in the original document: page number, and where available, bounding box or original character offset.

**Location**
: A human-checkable position in the original document: page (PDF), line range (text, code), section path (structured docs), and optional bounding box.

**Section path**
: The chain of headings that contain a piece of text, e.g. `["Lease agreement", "3. Payment", "3.2 Late fees"]`.

## Chunking and indexing

**Chunk**
: The unit of retrieval: a contiguous span `[start, end)` of a document's normalized text, with its section path and location. A chunk has a deterministic **chunk ID**.

**Context prefix**
: Optional text prepended to a chunk **for indexing only** (embedding and lexical index) to situate it within its document. It is never presented as source content and never quotable. See *contextual enrichment*.

**Contextual enrichment**
: Generating a context prefix per chunk with a language model, from the chunk and its document (after Anthropic's *Contextual Retrieval*).

**Embedding**
: A dense vector representing the meaning of a text, produced by an **embedder** identified by a **model ID** and dimension.

**Index**
: All persisted data of a corpus: documents, chunks, lexical index, vector index, manifest.

**Pipeline fingerprint**
: A hash of every setting that affects what is stored: parser identity and version, normalization version, chunker settings, enrichment settings, embedder model ID and dimension. Two indexes with the same fingerprint are built the same way.

**Manifest**
: The persisted record of an index's pipeline fingerprint and its components, schema version and statistics.

## Retrieval

**Query**
: The user's question as text, plus optional filters, conversation history and retrieval options.

**Search query**
: The text actually sent to retrievers. It may differ from the query after **query rewriting** (e.g. a follow-up condensed into a standalone question).

**Retriever**
: A component that returns a ranked list of chunks for a search query. Soundline has two built-in retriever kinds: **lexical** (full-text, BM25-like) and **dense** (vector similarity).

**Candidate**
: A chunk returned by at least one retriever, with its per-retriever ranks and scores.

**Fusion**
: Combining several ranked lists into one. Default: **Reciprocal Rank Fusion (RRF)**.

**Reranker**
: A model that re-scores `(query, chunk)` pairs jointly, more precisely than first-stage retrievers but more expensively.

**Hit**
: A candidate in the final ranked result of a search, with a final score and an **explanation** (how each stage scored it).

**Evidence**
: The ordered, deduplicated, budget-limited set of passages given to the language model for generation. Each piece of evidence has a short **evidence ID** (`E1`, `E2`…) scoped to one answer.

**Context window budget**
: The maximum number of tokens that evidence may occupy in the generation prompt.

## Generation

**Answer**
: The result of `ask`: a status, the answer text, the claims, the citations, the evidence used, and a trace.

**Answer status**
: `ANSWERED` (all claims supported), `PARTIAL` (some claims could not be supported and were removed or flagged), `ABSTAINED` (no answer given; with an **abstention reason**).

**Claim**
: A minimal unit of the answer that asserts something. Typically a sentence. Each claim carries zero or more citations.

**Citation**
: A link from a claim to evidence, consisting of an evidence ID and a **quote**: the exact text that supports the claim.

**Quote verification**
: Checking that a citation's quote occurs in the cited evidence (under normalization rules) and resolving it to an exact span and location in the source document.

**Verified citation**
: A citation whose quote passed verification. Only verified citations are returned to users.

**Abstention**
: A deliberate refusal to answer because the evidence is insufficient, with a machine-readable reason: `NO_EVIDENCE`, `LOW_RELEVANCE`, `MODEL_INSUFFICIENT_EVIDENCE`, `UNSUPPORTED_CLAIMS`.

## Evaluation

**Eval dataset (golden set)**
: A versioned collection of **eval cases**.

**Eval case**
: A question with its expected behavior: whether it is answerable, the **relevant quotes** (gold evidence, labeled by quote rather than chunk ID), an optional reference answer, and tags.

**Relevant quote**
: A short exact excerpt from a document that a correct answer must rely on. Labeling relevance by quote keeps datasets valid when chunking changes.

**Run**
: One execution of a dataset against one configuration, producing per-case results and aggregate metrics.

**Baseline**
: A stored run used as the reference for comparison.

**Judge**
: A language model, with a versioned rubric prompt, used to score generation quality (faithfulness, correctness).

**Regression gate**
: A rule that fails a comparison when a metric degrades beyond a tolerance with statistical confidence.

## Architecture

**Port**
: An interface the core depends on to reach the outside world (models, stores, parsers, clock).

**Adapter**
: An implementation of a port for a specific technology (SQLite, Anthropic, fastembed…).

**Fake**
: A lightweight, deterministic, in-memory adapter used in tests, verified by the same contract tests as real adapters.
