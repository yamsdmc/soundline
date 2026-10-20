# 11 — Testing strategy

## Purpose

Soundline is built with **test-driven development**, in the strict sense: no production code is written except to make a failing test pass, and design emerges from the tests through refactoring.

This chapter explains how we do that in a system whose core dependencies (language models, embedders) are nondeterministic, slow and paid for.

## Doctrine: Canon TDD

We follow Kent Beck's [Canon TDD](https://tidyfirst.substack.com/p/canon-tdd):

1. **Write a test list**: the scenarios the change must cover. Each spec chapter provides a starting list.
2. **Turn exactly one item into a concrete, runnable test.** Pick the item that teaches the most for the least effort.
3. **Make it pass** (and all previous tests) with the simplest change. Faking a return value is legitimate. **Triangulation** with a second example forces generalization.
4. **Refactor** to improve the design, with all tests green. This is where structure emerges: extracting concepts, naming them in the ubiquitous language, removing duplication.
5. **Repeat** until the list is empty. Add new items to the list as you discover them.

### What this means in practice

- **Do not implement the spec top-down.** The spec describes behaviors; it does not describe classes. If you find yourself creating `ChunkerFactory`, `AbstractBaseRetrieverStrategy` or similar before a test demanded it, stop.
- **The first test of a feature is usually embarrassingly simple** ("a one-line text yields one chunk"). That is the point: it fixes the interface while the implementation is trivial.
- **Do not anticipate.** The structural chunker's merging rules, the RRF formula, and the verification ladder each arrive one test at a time.
- **Refactoring is not optional.** A green bar with duplicated or poorly named code is half a cycle. Refactoring commits are separate from behavior commits.
- **A bug is a missing test.** Every bug fix starts with a failing test that reproduces it.

## Three feedback loops

```
┌───────────────────────────────────────────────────────────────────────┐
│  Loop 3 — Quality (evaluation)            minutes · real models       │
│  "Is it good?"  Benchmarks, metrics with CIs, regression gates        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Loop 1 — Acceptance (outer TDD loop)    seconds · fakes        │  │
│  │  "Does it do what the spec says?"  One test per behavior ID     │  │
│  │  ┌───────────────────────────────────────────────────────────┐  │  │
│  │  │  Loop 2 — Unit (inner TDD loop)       milliseconds        │  │  │
│  │  │  "Does this piece work?"  Domain logic, edge cases        │  │  │
│  │  └───────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### Loop 1: acceptance tests (outer loop)

- Written from spec behaviors, **before** implementing them. They stay red while the inner loop progresses (double-loop TDD).
- Exercise the system through **public interfaces only**: the Python facade, the CLI runner, the HTTP test client, the MCP client.
- Use **fakes** for all driven ports. They never touch the network.
- Grow a **domain-language test DSL** to stay readable. The example below is **illustrative only**: it shows the reading level we aim for, not an API to build. The first acceptance tests are written with plain fixtures, and the DSL is extracted from their duplication.
  ```python
  @pytest.mark.spec("GEN-033", "GEN-034")
  def test_unsupported_claim_is_dropped_and_answer_is_partial(soundline):
      soundline.given_document("lease.md", "Rent is due on the 5th. Pets are allowed.")
      soundline.given_model_answers(
          claim("Rent is due on the 5th.", cite("E1", "Rent is due on the 5th")),
          claim("Parking is free.", cite("E1", "Parking is free")),  # not in evidence
      )

      answer = soundline.ask("When is rent due?")

      assert answer.status is AnswerStatus.PARTIAL
      assert [c.text for c in answer.claims] == ["Rent is due on the 5th."]
      assert [d.text for d in answer.dropped_claims] == ["Parking is free."]
  ```
  If the extracted DSL ends up looking different, the extracted one wins.

### Loop 2: unit tests (inner loop)

- Drive domain and application code: normalization, chunking, fusion, filters, context assembly, verification, metrics, statistics, fingerprinting.
- Pure functions and value objects dominate the domain, so most unit tests need **no doubles at all**.
- Prefer **sociable** unit tests (real collaborators from the domain) over solitary ones. Doubles appear only at ports.

### Loop 3: quality (evaluation)

TDD answers "does it behave as specified?". It cannot answer "is the ranking good?" or "is the answer faithful?". Evaluation can:

- Retrieval benchmarks (deterministic, no LLM) run in CI on every pull request against a committed smoke dataset.
- End-to-end benchmarks with real models run nightly and before releases, with results stored as baselines.
- A change motivated by quality ("rerank by default", "chunk at 384 tokens") MUST come with an evaluation comparison in its pull request.

## Test doubles

**Fakes over mocks.** Mocks that assert call sequences couple tests to implementation and break on every refactoring. Fakes are working, simplified implementations that let tests assert on **outcomes**.

| Port | Fake | Behavior |
|---|---|---|
| `Embedder` | `HashingEmbedder` | Deterministic bag-of-words feature hashing into a fixed dimension, L2-normalized. Shared words → higher cosine. An optional **synonym map** lets tests express semantic matches without lexical overlap (`{"pay": "payable", "rent": "loyer"}`) |
| `LanguageModel` | `ScriptedLanguageModel` | Returns pre-programmed responses, matched by predicate or in sequence. Records every request for assertions on prompts. Raises scripted errors (rate limit, timeout, invalid output) |
| `Reranker` | `OverlapReranker` | Scores by token overlap with the query |
| Stores | `InMemoryStore` | Implements `DocumentStore`, `LexicalIndex` (simple BM25) and `VectorIndex` (brute-force cosine), with transactional semantics and **fault injection** (crash after step N) |
| `Parser` | real parsers on small fixtures | Parsers are pure. Fixtures are tiny files committed in `tests/fixtures/` |
| `Clock` | `FrozenClock` | Fixed, advanceable time |
| `Tracer` | `RecordingTracer` | Records spans for assertions on trace structure |
| `Cache` | `InMemoryCache` | Dictionary, with hit and miss counters |
| `SourceReader` | `InMemorySources` | Maps URIs to bytes; supports mutation to simulate file changes |

### Fakes are verified

A fake that drifts from reality makes tests lie. Therefore:

- **Every fake passes the same contract test suite as the real adapters** of its port.
- Contract suites are written as abstract test classes, parametrized per adapter:
  ```python
  class VectorIndexContract:
      @pytest.fixture
      def index(self) -> VectorIndex:
          raise NotImplementedError

      def test_nearest_vector_ranks_first(self, index): ...
      def test_filters_apply_before_limit(self, index): ...


  class TestInMemoryVectorIndex(VectorIndexContract): ...


  class TestSqliteVectorIndex(VectorIndexContract): ...


  @pytest.mark.postgres
  class TestPostgresVectorIndex(VectorIndexContract): ...
  ```
- Contract suites are **public** (`soundline.testing.contracts`, API-020), so third-party adapters are held to the same standard.

## Testing the nondeterministic parts

| Concern | Technique |
|---|---|
| Prompt construction | **Approval (snapshot) tests** on rendered prompts. A prompt change shows up as a reviewable diff and requires a `prompt_version` bump |
| Model output handling | `ScriptedLanguageModel` covering valid, invalid, partial, truncated, refusing and adversarial outputs |
| Real provider adapters | **Recorded interactions** (VCR-style cassettes, secrets scrubbed) replayed in CI. Live tests are opt-in (`pytest -m live`) and run nightly with real keys |
| Retrieval quality | Loop 3 (evaluation), never asserted in unit tests with real models |
| Embedding adapters | Contract: dimension, normalization, determinism for the same input, batch = individual results within tolerance |

## Property-based testing

[Hypothesis](https://hypothesis.readthedocs.io) is used wherever the spec states an **invariant** (`INV-*`). Property tests complement examples; they do not replace them:

- Example tests drive the design (TDD).
- Property tests then attack it with generated inputs: random Unicode, empty sections, giant tokens, adversarial whitespace, random rankings, random scripted quotes.

Custom strategies (`documents()`, `markdown_documents()`, `rankings()`, `filters()`) live in `soundline.testing.strategies` and are public.

## Mutation testing

Coverage says which lines ran, not whether tests would notice a bug. **Mutation testing** ([mutmut](https://github.com/boxed/mutmut)) measures that:

- Runs on `soundline/domain` weekly and before releases.
- Target: **≥ 90% killed mutants** in the domain. Surviving mutants are triaged: missing test, equivalent mutant (annotated), or dead code (removed).

## Coverage

Coverage is an **outcome of TDD, not a goal**. It is reported (branch coverage) but not used as a merge gate, which would encourage tests written for coverage. In practice, strict TDD yields > 95% in the domain. A drop is a signal to investigate, not a rule to satisfy.

## Test organization and conventions

```
tests/
  acceptance/        # by chapter: test_ingestion.py, test_retrieval.py…
  unit/              # mirrors src/soundline/domain and application as they emerge
  contract/          # one module per port, applying public contract suites
  integration/       # real adapters: sqlite (always), postgres (testcontainers, marker), providers (cassettes)
  fixtures/          # tiny documents: txt, md, html, pdf (3 pages), docx, scanned.pdf, adversarial/
  approvals/         # approved prompt snapshots
```

- **Test names are behavior sentences**: `test_reingesting_unchanged_document_is_a_noop`, not `test_ingest_2`.
- **Arrange / Act / Assert**, one behavior per test, and one act.
- **Spec traceability**: `@pytest.mark.spec("ING-007")` on acceptance tests (see the [spec README](README.md)).
- **No network** in the default run: enforced with `pytest-socket`. Markers `postgres`, `live`, `slow` opt in.
- **No sleeping**: time comes from `Clock`, and retries use an injectable backoff schedule.
- **Fast**: default suite < 60 s (OPS-006). A test slower than 1 s needs justification or the `slow` marker.
- **Deterministic**: randomness is seeded. Hypothesis runs with a stable profile in CI, plus an extended profile nightly.

## Commit discipline

- Every commit on `main` is green.
- Behavior changes and refactorings are **separate commits** ("tidy first"), so reviewers can see that refactorings changed no behavior.
- Conventional commit messages (`feat(retrieval): …`, `refactor(chunking): …`, `test(eval): …`), with behavior IDs where relevant.
- Pull requests that change behavior show the red test first (in the description or as the first commit) and reference spec IDs.

## Example: driving RRF test-first

How `RET-030` unfolds in the inner loop:

1. **Test**: a single list `[a]` fuses to `[a]`. **Code**: return the first list. *(Fake it.)*
2. **Test**: two lists `[a, b]` and `[b, a]` with equal weights → tie, broken by chunk ID → `[a, b]`. **Code**: still passes trivially. This is not enough: the test list gets a new item.
3. **Test**: `[a, b]` and `[b, c]` → `b` first (in both lists). **Code**: now real scoring is needed: `Σ 1/(60 + rank)`. *(Triangulation forces the formula.)*
4. **Test**: exact scores for a worked example with ranks 1 and 3 → `1/61 + 1/63`. **Code**: passes. Refactor: extract `RankedList`, name `rrf_k`.
5. **Test**: weight 0 for one list equals the other list alone. **Code**: add weights.
6. **Property**: INV-RET-1 and INV-RET-2 with generated rankings.

At no point was a `FusionStrategy` hierarchy designed. If a second fusion method arrives (RET-033), the abstraction is extracted **then**, from two concrete cases.

## Tooling

| Tool | Purpose |
|---|---|
| `uv` | Environments, locking, running |
| `pytest` (+ `pytest-xdist`, `pytest-socket`, `pytest-asyncio`) | Test runner |
| `hypothesis` | Property-based testing |
| `syrupy` (or equivalent) | Approval / snapshot tests |
| `vcrpy` | Recorded provider interactions |
| `testcontainers` | PostgreSQL integration tests |
| `mutmut` | Mutation testing |
| `ruff` | Lint and format |
| `pyright` (strict) | Type checking |
| `import-linter` | Architecture rules (ARC-005) |
| `scripts/spec_coverage.py` | Behavior ID ↔ test traceability |
