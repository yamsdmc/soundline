import json
import re
from dataclasses import asdict
from pathlib import Path

from soundline.application.ports import Generation
from soundline.domain.calibration import Calibration
from soundline.domain.errors import ConfigurationError
from soundline.domain.runs import EvalRun
from soundline.domain.usage import TokenUsage


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

    def save_calibration(self, calibration: Calibration) -> None:
        path = self._calibration_path(calibration.judge_model, calibration.judge_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(calibration.to_dict(), indent=2, sort_keys=True))

    def calibration(self, judge_model: str, judge_version: str) -> Calibration | None:
        path = self._calibration_path(judge_model, judge_version)
        if not path.is_file():
            return None
        return Calibration.from_dict(json.loads(path.read_text()))

    def _calibration_path(self, judge_model: str, judge_version: str) -> Path:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{judge_model}__{judge_version}")
        return self._directory.parent / "calibrations" / f"{slug}.json"


class JsonGenerationCache:
    """One JSON file per cached model output, under `directory` (EVL-061)."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get(self, key: str) -> Generation | None:
        path = self._path(key)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Generation(data["text"], TokenUsage(**data["usage"]), data.get("latency_ms"))

    def put(self, key: str, generation: Generation) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "text": generation.text,
            "usage": asdict(generation.usage),
            "latency_ms": generation.latency_ms,
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _path(self, key: str) -> Path:
        return self._directory / key[:2] / f"{key}.json"
