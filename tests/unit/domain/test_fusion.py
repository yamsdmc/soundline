import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.fusion import fuse

rankings = st.lists(st.sampled_from("abcdefgh"), unique=True, max_size=8)


@pytest.mark.spec("RET-030")
def test_a_single_ranking_keeps_its_order():
    assert [hit.item for hit in fuse({"lexical": ["a", "b"]})] == ["a", "b"]


@pytest.mark.spec("RET-030", "RET-031")
def test_an_item_found_by_both_retrievers_outranks_items_found_by_one():
    fused = fuse({"lexical": ["a", "b"], "dense": ["b", "c"]})

    assert [hit.item for hit in fused] == ["b", "a", "c"]


@pytest.mark.spec("RET-030")
def test_the_fused_score_is_the_sum_of_reciprocal_ranks_with_k_60():
    fused = fuse({"lexical": ["x", "a"], "dense": ["y", "z", "a"]})

    assert next(hit for hit in fused if hit.item == "a").score == pytest.approx(1 / 62 + 1 / 63)


@pytest.mark.spec("RET-006")
def test_ties_are_broken_by_item_id_whatever_the_input_order():
    fused = fuse({"lexical": ["b", "a"], "dense": ["a", "b"]})

    assert [hit.item for hit in fused] == ["a", "b"]


@pytest.mark.spec("RET-032")
def test_a_zero_weight_disables_a_retriever():
    fused = fuse({"lexical": ["a", "b"], "dense": ["c", "b"]}, weights={"dense": 0.0})

    assert [hit.item for hit in fused] == ["a", "b"]


@pytest.mark.spec("RET-005")
def test_each_hit_explains_its_rank_in_every_retriever_including_absences():
    fused = fuse({"lexical": ["a", "b"], "dense": ["b"]})

    assert {hit.item: hit.ranks for hit in fused} == {
        "b": {"lexical": 2, "dense": 1},
        "a": {"lexical": 1, "dense": None},
    }


@pytest.mark.spec("INV-RET-2")
@given(lexical=rankings, dense=rankings)
def test_fusion_is_a_permutation_of_the_union_of_its_inputs(lexical: list[str], dense: list[str]):
    fused = [hit.item for hit in fuse({"lexical": lexical, "dense": dense})]

    assert sorted(fused) == sorted(set(lexical) | set(dense))


@pytest.mark.spec("INV-RET-6")
@given(lexical=rankings, dense=rankings, ignored=rankings)
def test_adding_a_zero_weight_retriever_never_changes_the_result(
    lexical: list[str], dense: list[str], ignored: list[str]
):
    base = fuse({"lexical": lexical, "dense": dense})
    extended = fuse(
        {"lexical": lexical, "dense": dense, "rerank": ignored}, weights={"rerank": 0.0}
    )

    assert [(h.item, h.score) for h in extended] == [(h.item, h.score) for h in base]
