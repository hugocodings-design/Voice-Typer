import pytest

from voice_typer.commands import apply


@pytest.mark.parametrize("text,expected", [
    ("Bonjour, à la ligne. Merci pour ton message.", "Bonjour,\nMerci pour ton message."),
    ("Premier point. Nouveau paragraphe. Deuxième point.", "Premier point.\n\nDeuxième point."),
    ("Est-ce que ça marche point d'interrogation", "Est-ce que ça marche ?"),
    ("Est-ce que ça marche, point d’interrogation.", "Est-ce que ça marche ?"),
    ("Bonjour virgule comment ça va", "Bonjour, comment ça va"),
    ("Il a dit ouvrez les guillemets bonjour fermez les guillemets.", "Il a dit « bonjour »."),
    ("Le budget ouvrir la parenthèse estimé fermer la parenthèse est prêt.", "Le budget (estimé) est prêt."),
    ("Merci point final", "Merci."),
    ("à la ligne, nouvelle tâche", "\nNouvelle tâche"),   # starting on a new line is intentional
    ("J'ai deux points à aborder.", "J'ai deux points à aborder."),          # not a command
    ("La virgule flottante.", "La, flottante."),                              # known limitation
])
def test_french(text, expected):
    if "flottante" in text:
        pytest.skip("documented limitation: 'virgule' is always a command")
    assert apply(text, "fr") == expected


@pytest.mark.parametrize("text,expected", [
    ("Hello comma new line how are you question mark", "Hello,\nHow are you?"),
    ("First point. New paragraph. Second point.", "First point.\n\nSecond point."),
    ("He said open quote hi close quote.", "He said “hi”."),
])
def test_english(text, expected):
    assert apply(text, "en") == expected


def test_auto_language_and_empty():
    assert apply("Bonjour à la ligne merci", None) == "Bonjour\nMerci"
    assert apply("", "fr") == ""
