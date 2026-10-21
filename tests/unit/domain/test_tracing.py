import pytest

from soundline.domain.tracing import Tracer, render_tree


class FakeClock:
    """Each reading advances by the next scripted step, in seconds."""

    def __init__(self, *steps: float) -> None:
        self._now = 0.0
        self._steps = list(steps)

    def __call__(self) -> float:
        self._now += self._steps.pop(0) if self._steps else 0.0
        return self._now


@pytest.mark.spec("OBS-001")
def test_spans_nest_and_measure_their_duration():
    tracer = Tracer(clock=FakeClock(0, 0, 0.003, 0, 0.012, 0))

    with tracer.span("soundline.search"):
        with tracer.span("embed query"):
            pass
        with tracer.span("dense", hits=5):
            pass

    root = tracer.root
    assert root is not None
    assert [child.name for child in root.children] == ["embed query", "dense"]
    assert root.children[0].duration_ms == pytest.approx(3)
    assert root.children[1].attributes == {"hits": 5}


@pytest.mark.spec("OBS-004")
def test_the_tree_shows_durations_attributes_and_marks_the_slowest_step():
    tracer = Tracer(clock=FakeClock(0, 0, 0.003, 0, 0.012, 0, 0.001, 0))

    with tracer.span("soundline.search"):
        with tracer.span("embed query"):
            pass
        with tracer.span("dense", hits=5):
            pass
        with tracer.span("fuse"):
            pass

    assert render_tree(tracer.root) == (  # type: ignore[arg-type]
        "soundline.search [16 ms]\n"
        "├─ embed query [3 ms]\n"
        "├─ dense [12 ms, hits=5] ← slowest\n"
        "└─ fuse [1 ms]"
    )
