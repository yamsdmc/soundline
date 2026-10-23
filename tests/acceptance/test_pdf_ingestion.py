import pytest

from soundline import Soundline
from soundline.domain.answers import answer_to_dict
from soundline.interfaces.answer_text import answer_text
from soundline.testing import ScriptedLanguageModel

PAGES = [
    "Bail d'habitation\n\nLe loyer est payable le 5 de chaque mois.",
    "Le dépôt de garantie est rendu dans un délai de 1 mois.",
]


def citing(quote: str) -> dict[str, object]:
    return {
        "claims": [
            {
                "text": "Le délai est de 1 mois.",
                "citations": [{"evidence_id": "E1", "quote": quote}],
            }
        ],
        "insufficient_evidence": None,
    }


@pytest.mark.spec("ING-025", "ING-047")
def test_pages_ingested_are_searchable_and_each_hit_knows_its_pages():
    soundline = Soundline.in_memory(llm=ScriptedLanguageModel())
    soundline.ingest_pages("bail.pdf", PAGES)

    [hit] = soundline.search("dépôt de garantie", k=1)

    assert hit.chunk.pages[-1][0] == 2


@pytest.mark.spec("ING-047", "GEN-031", "GEN-042")
def test_a_citation_from_a_pdf_names_its_page_in_text_and_json():
    soundline = Soundline.in_memory(
        llm=ScriptedLanguageModel(citing("rendu dans un délai de 1 mois"))
    )
    soundline.ingest_pages("bail.pdf", PAGES)

    answer = soundline.ask("Quel délai pour le dépôt de garantie ?")

    assert answer.citations[0].page == 2
    assert '[1] bail.pdf, p. 2: "rendu dans un délai de 1 mois"' in answer_text(answer)
    assert answer_to_dict(answer)["citations"][0]["page"] == 2  # type: ignore[index]


@pytest.mark.spec("CLI-007", "ING-047")
def test_the_viewer_names_the_page_of_each_source():
    soundline = Soundline.in_memory(
        llm=ScriptedLanguageModel(citing("rendu dans un délai de 1 mois"))
    )
    soundline.ingest_pages("bail.pdf", PAGES)

    html = soundline.viewer_html(soundline.ask("Quel délai pour le dépôt de garantie ?"))

    assert "bail.pdf &middot; p. 2" in html
