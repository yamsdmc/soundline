"""The `soundline` command line (docs/spec/08-interfaces.md). It only talks to the facade."""

import json
import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from soundline import Soundline
from soundline.api import DEFAULT_EMBEDDER, embedder_from_spec
from soundline.application.ingest import IngestionReport, IngestionStatus
from soundline.domain.errors import ConfigurationError, IndexMismatchError, SoundlineError
from soundline.domain.filters import InvalidFilterError

# Exit codes (CLI-001)
USAGE_ERROR = 2
CONFIGURATION_ERROR = 3
PARTIAL_SUCCESS = 5

app = typer.Typer(no_args_is_help=True, help="The eval-first RAG engine.")
inspect_app = typer.Typer(no_args_is_help=True, help="Inspect index internals.")
app.add_typer(inspect_app, name="inspect")

JsonOption = Annotated[bool, typer.Option("--json", help="Print one JSON document on stdout.")]
Paths = Annotated[list[Path], typer.Argument(help="Files and directories.")]


@contextmanager
def _soundline() -> Generator[Soundline]:
    home = os.environ.get("SOUNDLINE_HOME", ".soundline")
    embedder = os.environ.get("SOUNDLINE_EMBEDDER", DEFAULT_EMBEDDER)
    try:
        with Soundline.open(home, embedder=embedder_from_spec(embedder)) as soundline:
            yield soundline
    except InvalidFilterError as error:
        _fail(error, USAGE_ERROR)
    except (ConfigurationError, IndexMismatchError) as error:
        _fail(error, CONFIGURATION_ERROR)


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
        hits = soundline.search(query, k=k, filters=filters)
    if as_json:
        typer.echo(json.dumps({"hits": [hit.to_dict() for hit in hits]}))
        return
    for rank, hit in enumerate(hits, 1):
        where = " > ".join(hit.section_path) or "-"
        ranks = ", ".join(f"{name} {r or '-'}" for name, r in hit.ranks.items())
        typer.echo(f"{rank}. {hit.source}  [{where}]  score {hit.score:.4f} ({ranks})")
        typer.echo(f"   {hit.text[:200]}")


@inspect_app.command("manifest", help="How the index was built (STO-004).")
def inspect_manifest(as_json: JsonOption = False) -> None:
    with _soundline() as soundline:
        manifest = soundline.manifest()
    if manifest is None:
        typer.echo("{}" if as_json else "empty index: no manifest yet")
        return
    typer.echo(json.dumps(manifest.components, indent=None if as_json else 2, sort_keys=True))


def main() -> None:
    sys.exit(app())
