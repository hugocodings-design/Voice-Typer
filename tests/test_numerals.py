"""Numbers said in words are written in digits (numerals.py)."""

import pytest

from voice_typer.numerals import to_digits

NB = " "


@pytest.mark.parametrize("said, written", [
    ("J'ai vingt-cinq ans", "J'ai 25 ans"),
    ("Il y a quatre-vingt-dix-sept personnes", "Il y a 97 personnes"),
    ("soixante et onze euros", "71 euros"),
    ("vingt et un jours", "21 jours"),
    ("trente-et-un", "31"),
    ("septante-sept", "77"),
    ("quatre-vingts", "80"),
    ("dix-sept heures trente", "17 heures 30"),
    ("deux mille vingt-quatre", "2024"),
    ("douze mille cinq cents", f"12{NB}500"),
    ("un million deux cent mille", f"1{NB}200{NB}000"),
    ("deux millions de dollars", "2 millions de dollars"),
    ("Deux personnes", "2 personnes"),
    ("vingt-quatre heures sur vingt-quatre", "24 heures sur 24"),
    ("Il a cent ans", "Il a 100 ans"),
])
def test_french_numbers(said, written):
    assert to_digits(said, "fr") == written


def test_decimals_and_percent():
    assert to_digits("trois virgule cinq pour cent", "fr") == f"3,5{NB}%"
    assert to_digits("cinquante pour cent", "fr") == f"50{NB}%"
    assert to_digits("cent pour cent", "fr") == f"100{NB}%"
    assert to_digits("un virgule deux", "fr") == "1,2"
    assert to_digits("three point five percent", "en") == "3.5%"


def test_words_that_are_not_numbers_stay():
    assert to_digits("un rendez-vous à neuf heures", "fr") == "un rendez-vous à 9 heures"
    assert to_digits("une pomme et une poire", "fr") == "une pomme et une poire"
    assert to_digits("un vélo neuf.", "fr") == "un vélo neuf."
    assert to_digits("un vélo neuf et rapide", "fr") == "un vélo neuf et rapide"
    assert to_digits("mille mercis", "fr") == "mille mercis"
    assert to_digits("repartir à zéro", "fr") == "repartir à zéro"
    assert to_digits("les deux-roues et trois-quarts", "fr") == "les deux-roues et trois-quarts"
    assert to_digits("one of them has twenty-one cats", "en") == "one of them has 21 cats"
    assert to_digits("il en reste deux un peu plus loin", "fr") == "il en reste 2 un peu plus loin"


def test_sequences_stay_separate():
    assert to_digits("un deux trois", "fr") == "1 2 3"
    assert to_digits("zéro six douze", "fr") == "0 6 12"


def test_english():
    assert to_digits("a hundred and five", "en") == "105"
    assert to_digits("two thousand and five", "en") == "2005"
    assert to_digits("twelve thousand five hundred", "en") == "12,500"
    assert to_digits("nineteen eighty-four", "en") == "1984"
    assert to_digits("twenty twenty-four", "en") == "2024"
    assert to_digits("fifty cents", "en") == "50 cents"


def test_auto_language_mixes_both():
    assert to_digits("fifty cents", None) == "50 cents"
    assert to_digits("deux cents personnes", None) == "200 personnes"
    assert to_digits("vingt-deux and twenty-two", None) == "22 and 22"


def test_digits_already_written_are_untouched():
    assert to_digits("Rendez-vous le 12 à 14 h 30, 3,5 %", "fr") == "Rendez-vous le 12 à 14 h 30, 3,5 %"


def test_setting_on_by_default_and_portable():
    from voice_typer.config import Config
    from voice_typer.transfer import PORTABLE

    assert Config().numbers_as_digits is True
    assert "numbers_as_digits" in PORTABLE
