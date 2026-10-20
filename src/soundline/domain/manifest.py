import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self, cast


@dataclass(frozen=True)
class Manifest:
    """How an index was built: every component that affects stored data (STO-001, STO-002)."""

    components: Mapping[str, object]

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.components, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def differences(self, other: "Manifest") -> list[str]:
        """Names of the components that differ, sorted."""
        names = set(self.components) | set(other.components)
        return sorted(n for n in names if self.components.get(n) != other.components.get(n))

    def to_json(self) -> str:
        return json.dumps(self.components, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls(cast("dict[str, object]", json.loads(text)))
