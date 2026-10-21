import pytest

from soundline.domain.languages import detect_language, language_name


@pytest.mark.spec("GEN-015")
@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("Dans quel délai le propriétaire doit-il rendre le dépôt de garantie ?", "fr"),
        ("When is the rent due?", "en"),
        ("¿Cuándo se paga el alquiler del piso?", "es"),
        ("Wann muss der Vermieter die Kaution zurückzahlen?", "de"),
        ("Quando il proprietario deve restituire il deposito?", "it"),
        ("Quando o senhorio tem de devolver a caução?", "pt"),
    ],
)
def test_the_language_of_a_question_is_detected_from_its_function_words(
    question: str, language: str
):
    assert detect_language(question) == language


@pytest.mark.spec("GEN-015")
@pytest.mark.parametrize("question", ["", "RRF k=60?", "dépôt", "a"])
def test_no_language_is_guessed_without_enough_signal(question: str):
    assert detect_language(question) is None


def test_languages_have_english_names_for_the_prompt():
    assert language_name("fr") == "French"
