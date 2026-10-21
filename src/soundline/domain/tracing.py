"""Traces of one operation as a tree of timed steps (OBS-001, OBS-004)."""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class TraceSpan:
    name: str
    attributes: dict[str, object] = field(default_factory=dict[str, object])
    children: list["TraceSpan"] = field(default_factory=list["TraceSpan"])
    duration_ms: float = 0.0


class Tracer:
    """Records nested spans; `clock` returns seconds and is injectable for tests."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._stack: list[TraceSpan] = []
        self.root: TraceSpan | None = None

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[TraceSpan]:
        current = TraceSpan(name, dict(attributes))
        if self._stack:
            self._stack[-1].children.append(current)
        else:
            self.root = current
        self._stack.append(current)
        started = self._clock()
        try:
            yield current
        finally:
            current.duration_ms = (self._clock() - started) * 1000
            self._stack.pop()


def render_tree(root: TraceSpan) -> str:
    """The trace as an indented tree; the slowest step of each level is marked."""
    lines = [_label(root)]
    lines.extend(_children(root, prefix=""))
    return "\n".join(lines)


def _children(span: TraceSpan, prefix: str) -> list[str]:
    lines: list[str] = []
    slowest = max(span.children, key=lambda child: child.duration_ms, default=None)
    for index, child in enumerate(span.children):
        last = index == len(span.children) - 1
        marker = " ← slowest" if child is slowest and len(span.children) > 1 else ""
        lines.append(f"{prefix}{'└─' if last else '├─'} {_label(child)}{marker}")
        lines.extend(_children(child, prefix + ("   " if last else "│  ")))
    return lines


def _label(span: TraceSpan) -> str:
    details = [f"{round(span.duration_ms)} ms"]
    details += [f"{key}={value}" for key, value in span.attributes.items()]
    return f"{span.name} [{', '.join(details)}]"
