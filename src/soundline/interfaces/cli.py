"""The `soundline` command line (docs/spec/08-interfaces.md). It only talks to the facade."""

import json
import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Annotated, NoReturn

import typer

from soundline import Soundline
from soundline.api import DEFAULT_EMBEDDER, embedder_from_spec, llm_from_spec
from soundline.application.ingest import IngestionReport, IngestionStatus
from soundline.domain.answers import AnswerStatus, answer_to_dict
from soundline.domain.datasets import DatasetError
from soundline.domain.errors import (
    ConfigurationError,
    GenerationError,
    IndexMismatchError,
    ProviderUnavailableError,
    SoundlineError,
)
from soundline.domain.filters import InvalidFilterError
from soundline.domain.runs import (
    RunMismatchError,
    compare_runs,
    comparison_markdown,
    gate,
    parse_rules,
)

# Exit codes (CLI-001)
USAGE_ERROR = 2
CONFIGURATION_ERROR = 3
PROVIDER_UNAVAILABLE = 4
PARTIAL_SUCCESS = 5
INTERNAL_ERROR = 10

app = typer.Typer(no_args_is_help=True, help="The eval-first RAG engine.")
inspect_app = typer.Typer(no_args_is_help=True, help="Inspect index internals.")
app.add_typer(inspect_app, name="inspect")
eval_app = typer.Typer(no_args_is_help=True, help="Measure retrieval quality.")
app.add_typer(eval_app, name="eval")
CHECK_FAILED = 1

JsonOption = Annotated[bool, typer.Option("--json", help="Print one JSON document on stdout.")]
Paths = Annotated[list[Path], typer.Argument(help="Files and directories.")]


@contextmanager
def _soundline() -> Generator[Soundline]:
    home = os.environ.get("SOUNDLINE_HOME", ".soundline")
    embedder = os.environ.get("SOUNDLINE_EMBEDDER", DEFAULT_EMBEDDER)
    llm_spec = os.environ.get("SOUNDLINE_LLM")
    try:
        llm = llm_from_spec(llm_spec) if llm_spec else None
        with Soundline.open(home, llm=llm, embedder=embedder_from_spec(embedder)) as soundline:
            yield soundline
    except (InvalidFilterError, DatasetError, RunMismatchError) as error:
        _fail(error, USAGE_ERROR)
    except (ConfigurationError, IndexMismatchError) as error:
        _fail(error, CONFIGURATION_ERROR)
    except ProviderUnavailableError as error:
        _fail(error, PROVIDER_UNAVAILABLE)
    except GenerationError as error:
        _fail(error, INTERNAL_ERROR)


def _fail(error: SoundlineError, exit_code: int) -> NoReturn:
    typer.echo(f"error[{error.code}]: {error}", err=True)  # logs go to stderr (CLI-002)
    raise typer.Exit(exit_code)


def _print_report(report: IngestionReport, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(report.to_dict()))
    else:
        for result in report.results:
            reason = f" ({result.reason})" if result.reason else ""
            typer.echo(f"{result.status.value:<9} {result.source}{reason}")
    if report.count(IngestionStatus.FAILED):
        raise typer.Exit(PARTIAL_SUCCESS)


def _ingestion_command(
    run: Callable[[Soundline, list[Path]], IngestionReport],
) -> Callable[[list[Path], bool], None]:
    def command(paths: Paths, as_json: JsonOption = False) -> None:
        with _soundline() as soundline:
            report = run(soundline, paths)
        _print_report(report, as_json)

    return command


app.command("ingest", help="Ingest files and directories. Never deletes.")(
    _ingestion_command(lambda soundline, paths: soundline.ingest(paths))
)
app.command("sync", help="Ingest, and delete documents whose files disappeared.")(
    _ingestion_command(lambda soundline, paths: soundline.sync(paths))
)


@app.command(help="Hybrid search, with an explanation of each hit.")
def search(
    query: str,
    k: Annotated[int, typer.Option("-k", help="Number of hits.")] = 8,
    filter_json: Annotated[
        str | None,
        typer.Option("--filter", help='Canonical JSON filter, e.g. {"eq": ["type", "x"]}.'),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    try:
        filters = json.loads(filter_json) if filter_json else None
    except json.JSONDecodeError as error:
        _fail(InvalidFilterError(f"--filter is not valid JSON: {error}"), USAGE_ERROR)
    with _soundline() as soundline:
        result = soundline.search_result(query, k=k, filters=filters)
    for warning in result.warnings:
        typer.echo(f"warning: {warning} (degraded result)", err=True)
    if as_json:
        hits_json = [hit.to_dict() for hit in result.hits]
        typer.echo(json.dumps({"hits": hits_json, "degraded": result.degraded}))
        return
    for rank, hit in enumerate(result.hits, 1):
        where = " > ".join(hit.section_path) or "-"
        ranks = ", ".join(f"{name} {r or '-'}" for name, r in hit.ranks.items())
        typer.echo(f"{rank}. {hit.source}  [{where}]  score {hit.score:.4f} ({ranks})")
        typer.echo(f"   {hit.text[:200]}")


@app.command(help="Create the Soundline home directory.")
def init() -> None:
    home = Path(os.environ.get("SOUNDLINE_HOME", ".soundline"))
    existed = home.is_dir()
    home.mkdir(parents=True, exist_ok=True)
    typer.echo(f"{'Already initialized' if existed else 'Initialized'}: {home.resolve()}")
    typer.echo('Next: soundline ingest <files or directories>, then soundline search "..."')


@app.command(help="Check storage, embedder and index with real calls.")
def doctor(as_json: JsonOption = False) -> None:
    with _soundline() as soundline:
        checks = soundline.diagnose()
    if as_json:
        typer.echo(json.dumps({"checks": [vars(check) for check in checks]}))
    else:
        for check in checks:
            typer.echo(f"{'ok  ' if check.ok else 'FAIL'} {check.name:<9} {check.detail}")
    if not all(check.ok for check in checks):
        raise typer.Exit(CONFIGURATION_ERROR)


@inspect_app.command("manifest", help="How the index was built (STO-004).")
def inspect_manifest(as_json: JsonOption = False) -> None:
    with _soundline() as soundline:
        manifest = soundline.manifest()
    if manifest is None:
        typer.echo("{}" if as_json else "empty index: no manifest yet")
        return
    typer.echo(json.dumps(manifest.components, indent=None if as_json else 2, sort_keys=True))


@app.command(help="A grounded answer whose every claim cites a verified quote.")
def ask(question: str, as_json: JsonOption = False) -> None:
    with _soundline() as soundline:
        answer = soundline.ask(question)
    if as_json:
        typer.echo(json.dumps(answer_to_dict(answer)))
        return
    if answer.status is AnswerStatus.ABSTAINED:
        reason = answer.abstention_reason.value if answer.abstention_reason else "unknown"
        typer.echo(f"No answer ({reason}). {answer.abstention_message or ''}".rstrip())
        return
    typer.echo(answer.text)
    typer.echo()
    for number, citation in enumerate(answer.citations, 1):
        where = " > ".join(citation.section_path)
        label = PurePosixPath(citation.source).name + (f", {where}" if where else "")
        marker = " (approximate)" if citation.approximate else ""
        typer.echo(f'[{number}] {label}: "{citation.quote}"{marker}')  # GEN-042
    if answer.dropped_claims:
        typer.echo()
        typer.echo(f"{answer.status.value}: unsupported claims were removed:")
        for claim in answer.dropped_claims:
            typer.echo(f"  - {claim}")


@eval_app.command("run", help="Evaluate retrieval on a JSONL dataset and store the run.")
def eval_run(
    dataset: Path,
    name: Annotated[str | None, typer.Option(help="Run name (default: a timestamp).")] = None,
    allow_missing_sources: Annotated[
        bool,
        typer.Option(help="Score quotes from documents absent from the index as misses."),
    ] = False,
    as_json: JsonOption = False,
) -> None:
    with _soundline() as soundline:
        run = soundline.evaluate(dataset, name, allow_missing_sources=allow_missing_sources)
    if as_json:
        typer.echo(json.dumps(run.to_dict()))
        return
    typer.echo(f"run {run.name}: {run.dataset['cases']} cases, 95% bootstrap intervals")
    for metric, estimate in run.metrics.items():
        typer.echo(f"  {metric:<13} {estimate.mean:.3f}  [{estimate.low:.3f}, {estimate.high:.3f}]")


@eval_app.command("compare", help="Paired comparison of two runs on the same dataset.")
def eval_compare(
    baseline: str,
    run: str,
    output: Annotated[str, typer.Option("--format", help="text, md or json.")] = "text",
    tolerance: Annotated[
        float, typer.Option(help="Smallest difference worth a verdict (EVL-052).")
    ] = 0.02,
) -> None:
    with _soundline() as soundline:
        before, after = soundline.load_run(baseline), soundline.load_run(run)
        if output == "json":
            comparisons = compare_runs(before, after, tolerance)
            typer.echo(
                json.dumps(
                    {
                        m: {"verdict": c.verdict.value, "difference": vars(c.difference)}
                        for m, c in comparisons.items()
                    }
                )
            )
        else:
            typer.echo(comparison_markdown(before, after, tolerance))


@eval_app.command("gate", help="Exit 1 when a rule fails against the baseline (EVL-064).")
def eval_gate(
    run: str,
    baseline: Annotated[str, typer.Option(help="Baseline run name or JSON file.")],
    rules: Annotated[Path, typer.Option(help="TOML file of [[rule]] entries.")],
) -> None:
    with _soundline() as soundline:
        outcomes = gate(
            soundline.load_run(baseline), soundline.load_run(run), parse_rules(rules.read_text())
        )
    for outcome in outcomes:
        typer.echo(f"{'pass' if outcome.passed else 'FAIL'}  {outcome.explanation}")
    if not all(outcome.passed for outcome in outcomes):
        raise typer.Exit(CHECK_FAILED)


def main() -> None:
    sys.exit(app())
