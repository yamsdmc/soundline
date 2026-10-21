from soundline.domain.calibration import Calibration
from soundline.domain.errors import ConfigurationError
from soundline.domain.runs import EvalRun


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, EvalRun] = {}
        self._calibrations: dict[tuple[str, str], Calibration] = {}

    def save(self, run: EvalRun) -> str:
        self._runs[run.name] = run
        return f"memory:{run.name}"

    def load(self, name_or_path: str) -> EvalRun:
        if name_or_path not in self._runs:
            raise ConfigurationError(f"no evaluation run named {name_or_path!r}")
        return self._runs[name_or_path]

    def save_calibration(self, calibration: Calibration) -> None:
        self._calibrations[calibration.judge_model, calibration.judge_version] = calibration

    def calibration(self, judge_model: str, judge_version: str) -> Calibration | None:
        return self._calibrations.get((judge_model, judge_version))
