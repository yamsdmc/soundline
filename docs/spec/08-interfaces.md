# 08 — Interfaces

## Purpose

Expose the same capabilities consistently through four interfaces: **Python API**, **CLI**, **HTTP server** and **MCP server**. All four are thin driving adapters over the same application use cases (ARC-004). A behavior is never available in one interface with different semantics in another.

## Cross-interface rules

- **API-001** Concepts, names and defaults MUST be identical across interfaces (`k`, `filters`, `corpus`, statuses, error codes).
- **API-002** Filters use the canonical JSON form (RET-044) everywhere.
- **API-003** Errors map to stable codes everywhere: Python exception `code`, CLI exit code + JSON error, HTTP status + problem details body, MCP tool error.
- **API-004** Every result that has a trace exposes its `trace_id`.

## Python API

### Facade

```python
from soundline import Soundline, F

sl = Soundline.open("./.soundline")                # SQLite home, soundline.toml if present
sl = Soundline.from_config("soundline.toml")
sl = Soundline.in_memory(embedder=..., llm=...)    # tests, notebooks

report = sl.ingest(["./docs", "./notes.md"], corpus="default", metadata={"team": "legal"})
report = sl.sync("./docs", corpus="default")

hits   = sl.search("rent due date", k=5, filters=F.eq("type", "contract"))
answer = sl.ask("When is rent due?", corpus="default")

for event in sl.ask_stream("When is rent due?"):
    ...

chat = sl.conversation(corpus="default")
chat.ask("When is rent due?")
chat.ask("And if I'm late?")

sl.documents.list(corpus="default")
sl.documents.get(document_id)
sl.documents.delete(document_id)
sl.corpora.list() / .create(name) / .delete(name)

run = sl.evals.run("datasets/lease.jsonl")
diff = sl.evals.compare(run, "main")
```

- **API-010** Each method has an async twin on `AsyncSoundline` (`await sl.search(...)`, `async for event in sl.ask_stream(...)`).
- **API-011** Every returned object is an immutable, typed dataclass with a stable `to_dict()` and JSON schema.
- **API-012** `Soundline` is a context manager that releases resources (connections, thread pools) on exit.
- **API-013** Custom adapters can be injected programmatically: `Soundline.open(path, embedder=MyEmbedder(), llm=MyLLM())`. Injected adapters MUST satisfy the port protocols (checked at runtime with a clear error on mismatch).
- **API-014** The public API surface is everything importable from `soundline` and `soundline.testing`, and nothing else. Other modules are private and may change without notice.
- **API-016** A citation stays resolvable after its document is re-ingested: `sl.resolve(citation)` reports `current` (the revision is still live), `relocated` (the quote is found in the new revision; the new span is returned), or `stale` (the quote no longer exists in the live revision). Normalized text of superseded revisions is retained for a configurable period (default 30 days) so that stale citations can still display their original context.
- **API-015** Before 1.0, breaking changes are allowed in minor versions with changelog entries. From 1.0, Semantic Versioning applies strictly, and deprecations last at least one minor version with warnings.

### `soundline.testing`

- **API-020** Exposes the fakes (`HashingEmbedder`, `ScriptedLanguageModel`, `InMemoryStore`, `FrozenClock`, `RecordingTracer`…) and the **contract test suites** as importable base classes, so third parties can verify their own adapters:
  ```python
  from soundline.testing.contracts import EmbedderContract


  class TestMyEmbedder(EmbedderContract):
      @pytest.fixture
      def embedder(self):
          return MyEmbedder()
  ```

## CLI

Built with Typer. Global options: `--home <dir>` (default `./.soundline`, env `SOUNDLINE_HOME`), `--config <file>`, `--corpus <name>` (env `SOUNDLINE_CORPUS`), `--json`, `--quiet`, `--verbose`.

| Command | Description |
|---|---|
| `soundline init` | Create `soundline.toml` with commented defaults and the home directory. Interactive provider choice unless `--yes` |
| `soundline ingest <paths…> [--meta k=v] [--include g] [--exclude g]` | Ingest sources |
| `soundline sync <paths…>` | Ingest and delete vanished sources |
| `soundline search "<query>" [-k 5] [--filter JSON] [--explain]` | Show hits with scores and explanations |
| `soundline ask "<question>" [--filter JSON] [--format text\|md\|json] [--show-evidence] [--open]` | Grounded answer with citations. `--open` opens the citation viewer (CLI-007) |
| `soundline chat` | Interactive conversation (REPL) |
| `soundline documents list\|show\|delete` | Manage documents |
| `soundline corpus list\|create\|delete` | Manage corpora |
| `soundline inspect manifest\|chunk <id>\|document <id> [--chunks]` | Inspect index internals |
| `soundline reindex [--abort]` | Rebuild with the current configuration |
| `soundline gc` | Remove orphans |
| `soundline migrate` | Run storage migrations |
| `soundline export\|import <file>` | Portable archives |
| `soundline eval run\|compare\|gate\|sweep\|generate\|review\|calibrate\|baseline` | Evaluation (EVL chapter) |
| `soundline serve [--host] [--port]` | Start the HTTP server |
| `soundline mcp [--transport stdio\|http]` | Start the MCP server |
| `soundline doctor` | Check configuration, providers, credentials, extensions, index health |
| `soundline version` | Versions of Soundline, Python, adapters, extensions |

- **CLI-001** Exit codes: `0` success, `1` failure of the requested check (e.g. eval gate), `2` usage error, `3` configuration error, `4` provider unavailable, `5` partial success (some sources failed during ingestion), `10` internal error.
- **CLI-002** `--json` MUST print exactly one JSON document on stdout (or JSON Lines for streaming commands). Logs and progress go to stderr.
- **CLI-003** Colors and progress bars are disabled automatically when stdout is not a TTY, and with `NO_COLOR`.
- **CLI-004** `ask` without a configured language model fails with exit code 3 and a message explaining how to configure one. `search` works without any language model.
- **CLI-005** `soundline doctor` checks each configured component with a real minimal call (where cheap), and prints actionable fixes.
- **CLI-007** **Citation viewer.** `ask --open` writes a single self-contained HTML file (no network, no server) and opens it in the browser. It shows the answer, where clicking a claim highlights its citations, and next to it the cited source: for PDFs, the rendered page image with the quote highlighted at its bounding box; for other formats, the surrounding text with the quoted span highlighted. Approximate citations (GEN-038) and dropped claims are visibly marked. The same viewer is available from the Python API (`answer.to_html()`).
- **CLI-006** Destructive commands (`corpus delete`, `documents delete`, `sync` deletions above a threshold) require confirmation unless `--yes`.

## HTTP server

> **Scope: later.** Specified now so that use cases are designed for it (stateless requests, access checks inside use cases), but not built before 1.0.

Built with FastAPI. OpenAPI document served at `/openapi.json`, and documentation at `/docs`.

| Method & path | Description |
|---|---|
| `GET /health` | Liveness |
| `GET /ready` | Readiness (store reachable, manifest loaded) |
| `GET /v1/corpora` | List corpora |
| `POST /v1/corpora` | Create corpus |
| `DELETE /v1/corpora/{corpus}` | Delete corpus |
| `POST /v1/corpora/{corpus}/documents` | Upload documents (multipart, with metadata). Returns a job for large uploads |
| `GET /v1/corpora/{corpus}/documents` | List documents (paginated, filterable) |
| `GET /v1/corpora/{corpus}/documents/{id}` | Document details |
| `DELETE /v1/corpora/{corpus}/documents/{id}` | Delete document |
| `GET /v1/jobs/{id}` | Ingestion job status and report |
| `POST /v1/corpora/{corpus}/search` | Search |
| `POST /v1/corpora/{corpus}/ask` | Ask. `Accept: text/event-stream` streams GEN-050 events via SSE |
| `GET /v1/traces/{trace_id}` | Trace of a recent request (if trace retention is enabled) |

- **HTTP-001** Errors use RFC 9457 problem details (`application/problem+json`) with `type`, `title`, `status`, `detail` and the Soundline `code`.
- **HTTP-002** The HTTP server MUST NOT ingest from server-side file paths or arbitrary URLs given by clients (no path traversal, no SSRF). It ingests only uploaded content. URL ingestion MAY be enabled with an explicit allow-list.
- **HTTP-003** Authentication: none by default when bound to localhost. Binding to a non-loopback address without authentication configured MUST refuse to start unless `--insecure` is passed. Built-in auth: static API keys (bearer), each key scoped to a list of corpora and permissions (`read`, `write`, `admin`).
- **HTTP-004** Corpus access is enforced from the authenticated key **inside the use case** (not only at routing), so that no route can bypass it.
- **HTTP-005** Upload limits (size, count) and request timeouts are configurable. Defaults are conservative.
- **HTTP-006** List endpoints use cursor pagination.
- **HTTP-007** Request bodies and responses reuse the JSON schemas of the Python result types (API-011).

## MCP server

Exposes a corpus to agents through the Model Context Protocol. Transports: stdio (default) and streamable HTTP.

| Tool | Description |
|---|---|
| `search` | `query`, `k`, `filters`, `corpus` → hits with source labels, locations and text |
| `ask` | `question`, `filters`, `corpus` → grounded answer with verified citations |
| `get_document` | `document_id` → metadata and optionally a text range |
| `list_corpora` | Available corpora with descriptions |

Scope 0.1: stdio transport with `search`, `ask` and `list_corpora`. Scope later: streamable HTTP transport, `get_document`, resources.

Resources: each document is exposed as a resource (`soundline://<corpus>/<document_id>`), readable by span.

- **MCP-001** Tool descriptions MUST explain when to use `search` (the agent reasons over passages itself) versus `ask` (delegated grounded answer).
- **MCP-002** Tool results MUST present document text as quoted data with source labels, consistent with GEN-010, so that agents treat it as untrusted content.
- **MCP-003** The MCP server is read-only by default. Ingestion tools MAY be enabled explicitly.
- **MCP-004** Corpus descriptions (set with `soundline corpus describe`) are surfaced to agents to help tool selection.

## Test list (starting point)

1. Walking skeleton through the CLI: `ingest` a text file, then `ask`, prints an answer with one citation (fakes injected via a test config).
2. `search --json` prints exactly one JSON document matching the schema.
3. `ask` without an LLM configured → exit code 3 with guidance.
4. Partial ingestion failure → exit code 5, and the report lists the failure.
5. Python sync API works inside a running event loop (Jupyter-like).
6. `AsyncSoundline` and `Soundline` return equal results on the same fixture.
7. Injecting an object that does not satisfy `Embedder` → clear `ConfigurationError`.
8. HTTP `POST /search` with a filter returns the same hits as the Python API.
9. HTTP error → problem details with Soundline code.
10. HTTP server refuses to bind `0.0.0.0` without auth and without `--insecure`.
11. An API key scoped to corpus A gets 403 on corpus B, for every route (parametrized over the route table).
12. SSE stream emits GEN-050 events in order.
13. MCP `search` tool returns hits with labels; MCP is read-only by default.
14. Third-party adapter verified with an importable contract suite (example in `tests/`).
15. `resolve` reports `current`, `relocated` and `stale` for a citation after its document is edited in the three corresponding ways.
16. `answer.to_html()` produces a file with no external URL, containing each claim and its highlighted quote.
17. HTTP and MCP outputs carry UTF-16 offsets that differ from code-point offsets for text containing an emoji.
