"""The `soundline` command line (docs/spec/08-interfaces.md). It only talks to the facade."""

import json
import os
import sys
import webbrowser
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, NoReturn, cast

import typer

from soundline import Soundline
from soundline.api import DEFAULT_EMBEDDER, embedder_from_spec, llm_from_spec
from soundline.application.ask import GenerationSettings
from soundline.application.ingest import IngestionReport, IngestionStatus
from soundline.application.prompts import PromptTemplate
from soundline.domain.answers import Answer, AnswerStatus, answer_to_dict
from soundline.domain.datasets import DatasetError
from soundline.domain.errors import (
    ConfigurationError,
    GenerationError,
    IndexMismatchError,
    ProviderUnavailableError,
    SoundlineError,
)
from soundline.domain.events import AnswerCompleted, RetrievalCompleted, StreamError
from soundline.domain.filters import InvalidFilterError
from soundline.domain.runs import (
    RunMismatchError,
    compare_runs,
    comparison_markdown,
    gate,
    parse_rules,
)
from soundline.domain.tracing import render_tree
from soundline.domain.usage import Usage

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


def _home() -> Path:
    return Path(os.environ.get("SOUNDLINE_HOME", ".soundline"))


def open_in_browser(url: str) -> None:
    webbrowser.open(url)


@contextmanager
def _soundline() -> Generator[Soundline]:
    home = _home()
    embedder = os.environ.get("SOUNDLINE_EMBEDDER", DEFAULT_EMBEDDER)
    llm_spec = os.environ.get("SOUNDLINE_LLM")
    try:
        llm = llm_from_spec(llm_spec) if llm_spec else None
        prompt_dir = os.environ.get("SOUNDLINE_PROMPT")  # GEN-014
        generation = (
            GenerationSettings(prompt=PromptTemplate.from_directory(prompt_dir))
            if prompt_dir
            else None
        )
        with Soundline.open(
            home, llm=llm, embedder=embedder_from_spec(embedder), generation=generation
        ) as soundline:
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
    explain: Annotated[bool, typer.Option(help="Show each step and its duration.")] = False,
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
    if explain and result.trace is not None:
        typer.echo()
        typer.echo(render_tree(result.trace))


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
def ask(
    question: str,
    as_json: JsonOption = False,
    open_viewer: Annotated[
        bool, typer.Option("--open", help="Open the answer next to its highlighted sources.")
    ] = False,
) -> None:
    with _soundline() as soundline:
        answer = soundline.ask(question)
        if open_viewer:  # CLI-007
            page = _home() / "views" / datetime.now(UTC).strftime("answer-%Y%m%d-%H%M%S.html")
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(soundline.viewer_html(answer), encoding="utf-8")
            open_in_browser(page.resolve().as_uri())
    if answer.usage.stages:
        typer.echo(_usage_line(answer.usage), err=True)  # GEN-070, on stderr (CLI-002)
    if as_json:
        typer.echo(json.dumps(answer_to_dict(answer)))
        return
    _print_answer(answer)


@app.command(help="Converse: follow-ups are understood in context. Ctrl-D or /exit quits.")
def chat() -> None:
    with _soundline() as soundline:
        conversation = soundline.conversation()
        while (question := _read_question()) is not None:
            for event in conversation.ask_stream(question):
                if isinstance(event, RetrievalCompleted) and event.search_query != question:
                    typer.echo(f"searching: {event.search_query}")  # RET-071
                elif isinstance(event, StreamError):
                    raise event.error  # mapped to an exit code by _soundline
                elif isinstance(event, AnswerCompleted):
                    if event.answer.usage.stages:
                        typer.echo(_usage_line(event.answer.usage), err=True)
                    _print_answer(event.answer)
            typer.echo()


def _read_question() -> str | None:
    try:
        line = input("> ")
    except EOFError:
        return None
    question = line.strip()
    if question == "/exit":
        return None
    return question or _read_question()


def _print_answer(answer: Answer) -> None:
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


def _usage_line(usage: Usage) -> str:
    tokens = usage.tokens
    cached = tokens.cache_read + tokens.cache_write
    line = f"usage: {tokens.total_input:,} tokens in"
    line += f" ({cached:,} cached), " if cached else ", "
    line += f"{tokens.output:,} out"
    if usage.cost_usd is not None:
        return f"{line}, cost ${usage.cost_usd:.4f}"
    unpriced = sorted({stage.model for stage in usage.stages if stage.cost_usd is None})
    return f"{line}, cost unknown: no price for {', '.join(unpriced)}"


@eval_app.command(
    "run",
    help="Evaluate a JSONL dataset and store the run: end to end with a language model,"
    " retrieval-only without one.",
)
def eval_run(  # noqa: PLR0913, PLR0917  # one parameter per command-line option
    dataset: Path,
    name: Annotated[str | None, typer.Option(help="Run name (default: a timestamp).")] = None,
    allow_missing_sources: Annotated[
        bool,
        typer.Option(help="Score quotes from documents absent from the index as misses."),
    ] = False,
    retrieval_only: Annotated[
        bool, typer.Option(help="Search only; never call the language model (EVL-062).")
    ] = False,
    no_cache: Annotated[
        bool, typer.Option(help="Call the model again instead of reusing cached outputs.")
    ] = False,
    judge: Annotated[
        str | None,
        typer.Option(help="Judge model for faithfulness, e.g. anthropic:claude-opus-5-5."),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    with _soundline() as soundline:
        run = soundline.evaluate(
            dataset,
            name,
            allow_missing_sources=allow_missing_sources,
            retrieval_only=retrieval_only,
            no_cache=no_cache,
            judge=llm_from_spec(judge) if judge else None,
        )
    if as_json:
        typer.echo(json.dumps(run.to_dict()))
        return
    mode = run.settings.get("mode")
    model = f", model {run.settings['model']}" if "model" in run.settings else ""
    typer.echo(f"run {run.name} ({mode}{model}): {run.dataset['cases']} cases")
    judged = run.settings.get("judge")
    if isinstance(judged, Mapping):
        info = cast("Mapping[str, object]", judged)
        typer.echo(f"judge {info['model']} ({info['version']}, {info['calibration']})")
    for warning in run.warnings:
        typer.echo(f"warning: {warning}")
    typer.echo("metrics, 95% bootstrap intervals over the cases that define them:")
    width = max((len(metric) for metric in run.metrics), default=0)
    for metric, estimate in run.metrics.items():
        typer.echo(
            f"  {metric:<{width}} {estimate.mean:.3f}  [{estimate.low:.3f}, {estimate.high:.3f}]"
            f"  n={estimate.cases}"  # EVL-053
        )
    if run.operations:
        typer.echo("operations (mean, p50, p95, total):")  # EVL-030
        for metric, summary in run.operations.items():
            values = ", ".join(f"{summary[key]:,.4g}" for key in ("mean", "p50", "p95", "total"))
            typer.echo(f"  {metric:<{width}} {values}")


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
