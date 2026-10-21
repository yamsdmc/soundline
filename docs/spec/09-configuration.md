# 09 — Configuration and providers

## Purpose

Make Soundline work **with zero configuration** for search, and make every behavior **explicitly configurable** with validated, documented settings.

## Sources and precedence

- **CFG-001** Settings come from, highest precedence first: explicit arguments (Python, CLI flags, HTTP request options where allowed) → environment variables (`SOUNDLINE_` prefix, `__` for nesting, e.g. `SOUNDLINE_RETRIEVAL__RERANK_K=40`) → configuration file (`soundline.toml`, or `[tool.soundline]` in `pyproject.toml`) → built-in defaults.
- **CFG-002** The configuration file is located by: `--config` → `SOUNDLINE_CONFIG` → `./soundline.toml` → `./pyproject.toml [tool.soundline]`.
- **CFG-003** Configuration is validated at startup with precise errors (key path, expected type, received value, allowed values). Unknown keys are errors, which catches typos.
- **CFG-004** Secrets (API keys) MUST come from environment variables or a secrets file referenced by path. They MUST NOT be accepted in `soundline.toml` (validation error with guidance). Secrets MUST never appear in logs, traces, error messages or `doctor` output (masked).
- **CFG-005** `soundline config show` prints the effective configuration with the source of each value, secrets masked.
- **CFG-006** The effective configuration snapshot (secrets removed) is stored with each eval run and referenced in traces by hash.

## Reference configuration

```toml
# soundline.toml

[store]
backend = "sqlite"                  # "sqlite" | "postgres"
# path = ".soundline/index.db"
# dsn_env = "SOUNDLINE_PG_DSN"      # postgres: env var holding the DSN
# schema = "soundline"

[ingestion]
include = ["**/*"]
exclude = []
max_file_size_mb = 100
follow_symlinks = false

[parsing]
pdf = "soundline.pdf"               # or "docling"
detect_headers_footers = true

[chunking]
strategy = "structural"             # "structural" | "fixed" | "sentence" | "element"
max_tokens = 384                    # also capped by the embedder's own limit (ING-041)
min_tokens = 64
overlap_tokens = 64
section_split_level = 2

[enrichment]
enabled = false
model = "anthropic:claude-haiku-5-5"
max_document_tokens = 8000

[embedding]
model = "fastembed:intfloat/multilingual-e5-large"   # local, multilingual, MIT; see CFG-023
# English-only, much faster alternative: "fastembed:BAAI/bge-small-en-v1.5"
batch_size = 64
concurrency = 4

[retrieval]
k = 8
first_stage_k = 50
fusion = "rrf"                      # "rrf" | "weighted"
rrf_k = 60
weights = { lexical = 1.0, dense = 1.0 }
reranker = "none"                   # e.g. "fastembed:BAAI/bge-reranker-v2-m3" (multilingual), "cohere:rerank-v3.5"
rerank_k = 30
neighbour_expansion = 0
max_hits_per_document = 0           # 0 = unlimited
query_rewrite = "followups"         # "none" | "followups" | "multi"

[generation]
model = "anthropic:claude-sonnet-5-5"
context_budget_tokens = 6000
history_budget_tokens = 1500        # GEN-062
max_output_tokens = 1024
# no temperature: current Claude models reject sampling parameters; determinism comes from
# structured output and from caching model calls in evaluations (EVL-061)
fuzzy_quote_threshold = 0.9
fuzzy_min_chars = 30
citation_mode = "schema"            # "schema" | "native" (provider-native citations, GEN-022)
repair = false
min_relevance = 0.0                 # requires a reranker to be meaningful
instructions = ""
# prompt = "./prompts/house-v1"    # a template directory (system.txt, user.txt); its name is the prompt_version (GEN-014)

[evaluation]
judge_model = ""                    # empty = generation model (one API key); reports warn about self-judging (EVL-042)
bootstrap_resamples = 2000
seed = 42
allow_router_fallback = false     # CFG-015

[observability]
otel = false
trace_retention = 0                 # number of recent traces kept for inspection

[server]
host = "127.0.0.1"
port = 8484

[pricing]                           # USD per million tokens, overridable
# "anthropic:claude-sonnet-5-5" = { input = 0.0, output = 0.0 }
```

The values above are illustrative defaults. The generated `soundline.toml` from `soundline init` is the reference. Model defaults MUST be reviewed at each release.

## Providers

- **CFG-010** Model references use the form `<provider>:<model>` (e.g. `anthropic:claude-sonnet-5-5`, `openai:text-embedding-3-small`, `ollama:llama3.3`, `fastembed:BAAI/bge-small-en-v1.5`). The provider prefix selects the adapter.
- **CFG-011** OpenAI-compatible endpoints are configured with a named provider block, so local servers work without code:
  ```toml
  [providers.local]
  kind = "openai-compatible"
  base_url = "http://localhost:11434/v1"
  api_key_env = "OLLAMA_API_KEY"   # optional
  ```
  Then `model = "local:llama3.3"`.
- **CFG-012** Each provider block MAY set timeouts, max retries, max concurrency and rate limits (requests and tokens per minute). Soundline enforces client-side rate limiting.
- **CFG-013** A fully local setup (fastembed + Ollama, or another OpenAI-compatible local server) MUST be documented and covered by an integration test. This setup sends no data to any external service.
- **CFG-014** Using a provider whose extra is not installed fails with the exact `pip install "soundline[...]"` command (ARC-012).
- **CFG-015** **Routing providers** (OpenRouter, LiteLLM proxies and similar) MAY be used through the OpenAI-compatible adapter. Because a router can silently serve another model or provider:
  - each model call records the model **and** provider actually served, as returned by the router, in the trace and in eval runs (feeds EVL-056);
  - **automatic fallback is disabled during evaluation runs** (`soundline eval …`), so that results stay reproducible (EVL-061). A call that the router could only serve through a fallback fails instead. `evaluation.allow_router_fallback = true` overrides this, and the report then says so;
  - outside evaluation, fallbacks are allowed, and each one is recorded as a trace event.

## Defaults policy

- **CFG-020** Defaults favor **zero cost and zero network for ingestion and search** (local embeddings, no enrichment, no reranker by default).
- **CFG-021** Changing a default that affects the pipeline fingerprint is a **breaking change** (existing indexes would mismatch). It requires a changelog entry and a release note explaining how to keep the old behavior.
- **CFG-022** Every default MUST be justified by benchmark results or a documented rationale, in the configuration reference documentation.
- **CFG-023** Default models MUST satisfy: permissive license allowing commercial use (no non-commercial licenses), runnable on CPU, multilingual (at least EN, FR, DE, ES), and an input limit of at least 512 tokens. The license of every default and suggested model is listed in the documentation. The default embedder is chosen by benchmark among the candidates satisfying these constraints. `multilingual-e5-large` is the initial candidate. It is slower than small English models, which the quickstart documents along with the faster English-only option.
- **CFG-024** Default model choices are re-evaluated at each minor release. A change is a breaking change under CFG-021.

## Test list (starting point)

1. With no configuration file, `search` works with defaults.
2. Environment variable overrides a file value; an explicit argument overrides both.
3. Unknown key → error naming the key and suggesting the closest valid key.
4. An API key in `soundline.toml` → validation error with guidance.
5. `config show` masks secrets and shows value sources.
6. `local:` provider block routes to the OpenAI-compatible adapter with the configured base URL.
7. Changing `chunking.max_tokens` changes the fingerprint; changing `retrieval.k` does not.
7b. Fresh `soundline init` on a Python whose `sqlite3` cannot load extensions still produces a working index (ARC-014).
8. Missing extra → error with the exact install command.
