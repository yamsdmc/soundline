import pytest

from soundline.domain.manifest import Manifest

BUILT = Manifest(
    {
        "parser": "soundline.markdown@1",
        "chunker": {"strategy": "structural@1", "max_tokens": 384},
        "embedder": {"model_id": "hashing:256", "dimension": 256},
    }
)


@pytest.mark.spec("STO-002")
def test_the_same_components_give_the_same_fingerprint_whatever_their_order():
    reordered = Manifest(
        {
            "embedder": {"dimension": 256, "model_id": "hashing:256"},
            "chunker": {"max_tokens": 384, "strategy": "structural@1"},
            "parser": "soundline.markdown@1",
        }
    )

    assert reordered.fingerprint == BUILT.fingerprint


@pytest.mark.spec("STO-002")
def test_any_component_change_changes_the_fingerprint():
    smaller_chunks = {"strategy": "structural@1", "max_tokens": 128}
    changed = Manifest({**BUILT.components, "chunker": smaller_chunks})

    assert changed.fingerprint != BUILT.fingerprint


@pytest.mark.spec("STO-010")
def test_differences_name_the_components_that_changed():
    current = Manifest(
        {**BUILT.components, "embedder": {"model_id": "fastembed:e5", "dimension": 1024}}
    )

    assert BUILT.differences(current) == ["embedder"]
    assert BUILT.differences(BUILT) == []


def test_a_manifest_round_trips_through_json():
    assert Manifest.from_json(BUILT.to_json()) == BUILT
