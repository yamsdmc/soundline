import json
from pathlib import Path

from soundline.domain.errors import ConfigurationError
from soundline.domain.runs import EvalRun


class JsonRunStore:
    """Runs as JSON files in `directory` (EVL-060). A run is loaded by name or by path,
    so CI can compare against a baseline file committed to the repository."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, run: EvalRun) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{run.name}.json"
        path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True))
        return str(path)

    def load(self, name_or_path: str) -> EvalRun:
        path = Path(name_or_path)
        if not path.is_file():
            path = self._directory / f"{name_or_path}.json"
        if not path.is_file():
            raise ConfigurationError(f"no evaluation run named or located at {name_or_path!r}")
        return EvalRun.from_dict(json.loads(path.read_text()))
