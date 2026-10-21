.PHONY: check bench-trust

check:
	./scripts/check.sh

bench-trust:  ## The trust benchmark (EVL-092), local and free with Ollama
	./benchmarks/trust/run.sh
