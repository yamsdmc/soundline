import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from hypothesis import HealthCheck, settings

# "dev" is fast for the inner loop; "ci" is reproducible; "nightly" digs deeper.
settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=200, derandomize=True, print_blob=True)
settings.register_profile(
    "nightly", max_examples=5_000, suppress_health_check=[HealthCheck.too_slow]
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


APPROVALS = Path(__file__).parent / "approvals"


@pytest.fixture
def approve(request: pytest.FixtureRequest) -> Callable[[str], None]:
    """Approval test: compares text with `approvals/<test>.approved.txt`.

    On a mismatch, the actual text is written next to it as `.received.txt`; review the
    diff, then rename it to approve the change.
    """

    def verify(text: str) -> None:
        test = cast("pytest.Item", request.node)  # pyright: ignore[reportUnknownMemberType]
        name = re.sub(r"\W+", "_", test.name).strip("_")
        approved = APPROVALS / f"{name}.approved.txt"
        received = APPROVALS / f"{name}.received.txt"
        if approved.exists() and approved.read_text(encoding="utf-8") == text:
            received.unlink(missing_ok=True)
            return
        APPROVALS.mkdir(exist_ok=True)
        received.write_text(text, encoding="utf-8")
        pytest.fail(f"not approved: review {received} and rename it to {approved.name}")

    return verify
