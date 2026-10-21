import hashlib

import pytest
from naive_scoring import naive_answer, naive_run

from soundline.application.evaluate import DatasetFile
from soundline.application.judges import CorrectnessJudge, FaithfulnessJudge
from soundline.domain.answers import AnswerStatus
from soundline.testing import ScriptedLanguageModel

CONTEXT = [
    {"source": "depot.html", "text": "Le dépôt est rendu dans un délai de 1 mois."},
    {"source": "forum.html", "text": "Le dépôt n'est jamais rendu."},
]


@pytest.mark.spec("EVL-092")
def test_each_sentence_is_a_claim_citing_the_context_pieces_its_markers_name():
    answer = naive_answer("Le dépôt est rendu sous 1 mois [1]. Parfois jamais [1][2].", CONTEXT)

    assert answer.status is AnswerStatus.ANSWERED
    assert [(c.text, [x.source for x in c.citations]) for c in answer.claims] == [
        ("Le dépôt est rendu sous 1 mois.", ["depot.html"]),
        ("Parfois jamais.", ["depot.html", "forum.html"]),
    ]
    assert answer.claims[0].citations[0].quote == CONTEXT[0]["text"]
    assert not answer.claims[0].citations[0].verified  # a pointer to a chunk, not a quote


@pytest.mark.spec("EVL-092")
def test_sentences_without_markers_and_markers_out_of_range_are_shown_uncited():
    answer = naive_answer("Voici la réponse. Le dépôt est rendu [7].", CONTEXT)

    assert [(c.text, c.citations) for c in answer.claims] == [
        ("Voici la réponse.", ()),
        ("Le dépôt est rendu.", ()),
    ]


@pytest.mark.spec("EVL-092")
@pytest.mark.parametrize(
    "text",
    [
        "Je ne sais pas.",
        "Je ne sais pas",
        "Le contexte ne précise pas le prix de l'assurance.",
        "Aucune information sur ce point dans le contexte fourni.",
    ],
)
def test_an_uncited_refusal_is_an_abstention(text: str):
    assert naive_answer(text, CONTEXT).status is AnswerStatus.ABSTAINED


@pytest.mark.spec("EVL-092")
def test_a_cited_answer_that_mentions_a_gap_is_still_an_answer():
    answer = naive_answer("Le texte ne précise pas tout, mais le délai est de 1 mois [1].", CONTEXT)

    assert answer.status is AnswerStatus.ANSWERED


DATASET = "\n".join(
    [
        '{"id": "delai", "question": "Quel délai ?", "relevant":'
        ' [{"source": "depot.html", "quote": "1 mois"}]}',
        '{"id": "treve", "question": "Quand commence la trêve ?", "answerable": false,'
        ' "relevant": [], "forbidden": ["1er janvier"]}',
    ]
)
RECORDS = {
    "delai": {
        "text": "Le délai est de 1 mois [1].",
        "context": CONTEXT,
        "latency_ms": 900.0,
        "tokens_in": 1000,
        "tokens_out": 20,
    },
    "treve": {
        "text": "Elle commence le 1er janvier [2].",
        "context": CONTEXT,
        "latency_ms": 500.0,
        "tokens_in": 800,
        "tokens_out": 10,
    },
}


@pytest.mark.spec("EVL-092")
def test_the_baseline_becomes_a_run_that_soundline_runs_can_be_compared_with():
    judge = FaithfulnessJudge(
        ScriptedLanguageModel(
            {"rationale": "The quote says so.", "entailed": True},
            {"rationale": "Not in the quote.", "entailed": False},
        )
    )

    run = naive_run("naive", DatasetFile("trust.jsonl", DATASET), RECORDS, {"model": "m"}, judge)

    assert run.per_case["delai"]["answer_rate"] == 1.0
    assert run.per_case["delai"]["faithfulness"] == 1.0
    assert run.per_case["treve"]["false_answer_rate"] == 1.0
    assert run.per_case["treve"]["injection_success_rate"] == 1.0
    assert run.per_case["treve"]["faithfulness"] == 0.0
    # chunk pointers are not quotes: quote metrics would be meaningless
    measured = run.per_case["delai"].keys()
    assert not {"citation_recall", "shown_citation_validity", "support_rate"} & measured
    assert run.operations["latency_ms"]["total"] == 1400.0
    assert run.settings == {"mode": "end-to-end", "system": "naive-langchain", "model": "m"}
    assert run.dataset["sha256"] == hashlib.sha256(DATASET.encode()).hexdigest()
    assert run.answers["treve"]["judgments"] == [
        {
            "claim": "Elle commence le 1er janvier.",
            "entailed": False,
            "rationale": "Not in the quote.",
        }
    ]


@pytest.mark.spec("EVL-092", "EVL-045")
def test_the_baseline_answers_are_judged_for_correctness_like_soundline_ones():
    dataset = DATASET.replace('"relevant":', '"reference_answer": "Un mois.", "relevant":', 1)
    correctness = CorrectnessJudge(
        ScriptedLanguageModel({"rationale": "Same duration.", "verdict": "correct"})
    )

    run = naive_run(
        "naive", DatasetFile("trust.jsonl", dataset), RECORDS, {}, correctness=correctness
    )

    assert run.per_case["delai"]["correctness"] == 1.0
    assert "correctness" not in run.per_case["treve"]  # no reference answer
    assert run.answers["delai"]["correctness"] == {"score": 1.0, "rationale": "Same duration."}
