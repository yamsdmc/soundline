# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (with the pre-1.0 rules described in API-015).

## [Unreleased]

### Added

- Walking skeleton (M1), test-driven through the Python API: `Soundline.in_memory(llm=...)`, `ingest_text`, `ask`. Answers cite verbatim quotes verified against the evidence and resolved to document spans (GEN-030, GEN-031, GEN-032), rendered with `[n]` markers (GEN-040). An empty corpus abstains without calling the model (GEN-001). Public fakes `InMemoryIndex` and `ScriptedLanguageModel` in `soundline.testing`.
- Specification (`docs/spec`) and architecture decision records (`docs/adr`).
- Repository foundations (M0): packaging with uv and hatchling, ruff, pyright strict, pytest with Hypothesis profiles and network disabled, import-linter layer contracts, domain purity guard (ARC-001), spec traceability script, CI on Linux, macOS and Windows, SQLite extension probe (ARC-014 spike).
