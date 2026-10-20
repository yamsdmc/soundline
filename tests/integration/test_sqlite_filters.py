import json
import sqlite3

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from soundline.adapters.stores.sqlite import filter_to_sql
from soundline.domain.filters import (
    And,
    Compare,
    Exists,
    F,
    Filter,
    Member,
    Metadata,
    Not,
    Or,
    Scalar,
    matches,
)

keys = st.sampled_from(["type", "year", "tags", "signed", "score"])
texts = st.text(alphabet="abcAB", max_size=3)
scalars: st.SearchStrategy[Scalar] = st.one_of(
    texts,
    st.integers(-5, 5),
    st.floats(-5, 5, allow_nan=False, allow_infinity=False),
    st.booleans(),
)
metadata_values = st.one_of(scalars, st.lists(texts, max_size=3))
metadatas: st.SearchStrategy[Metadata] = st.dictionaries(keys, metadata_values, max_size=5)

leaves: st.SearchStrategy[Filter] = st.one_of(
    st.builds(Compare, st.sampled_from(["eq", "ne", "gt", "gte", "lt", "lte"]), keys, scalars),
    st.builds(
        Member, st.sampled_from(["in", "nin"]), keys, st.lists(scalars, max_size=3).map(tuple)
    ),
    st.builds(Exists, keys),
)
filters: st.SearchStrategy[Filter] = st.recursive(
    leaves,
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=3).map(lambda items: And(tuple(items))),
        st.lists(children, min_size=1, max_size=3).map(lambda items: Or(tuple(items))),
        children.map(Not),
    ),
    max_leaves=6,
)


def sql_verdict(condition: Filter, metadata: Metadata) -> bool:
    sql, params = filter_to_sql(condition, "m")
    query = f"select {sql} from (select ? as m)"
    row = sqlite3.connect(":memory:").execute(query, [*params, json.dumps(metadata)]).fetchone()
    return bool(row[0])


@pytest.mark.spec("RET-040", "RET-043", "STO-043")
@settings(max_examples=500)  # 50 examples missed a cross-type ordering bug in mutation testing
@given(condition=filters, metadata=metadatas)
@example(condition=F.lt("type", ""), metadata={"type": 0})  # SQLite orders numbers before text
@example(condition=~F.ne("tags", "a"), metadata={})  # a missing key must not become true twice
def test_sql_translation_agrees_with_the_domain_semantics(condition: Filter, metadata: Metadata):
    assert sql_verdict(condition, metadata) is matches(condition, metadata)
