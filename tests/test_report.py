from pathlib import Path
from urllib.parse import unquote

from voice_typer import report


def test_mailto_has_address_subject_and_description():
    url = report.mailto_url("Le bouton ne répond pas", "VoiceTyper-probleme.zip", attached=False)
    assert url.startswith(f"mailto:{report.SUPPORT_EMAIL}?subject=")
    text = unquote(url)
    assert "Le bouton ne répond pas" in text and "VoiceTyper-probleme.zip" in text and "à joindre" in text


def test_outlook_command_attaches_the_diagnostic():
    zip_path = Path("C:/Users/x/Downloads/VoiceTyper-probleme.zip")
    cmd = report.outlook_command("OUTLOOK.EXE", "Rien ne s'écrit", zip_path)
    assert cmd[:4] == ["OUTLOOK.EXE", "/c", "ipm.note", "/m"]
    assert cmd[4].startswith(report.SUPPORT_EMAIL + "&subject=") and "&body=" in cmd[4]
    assert cmd[5:] == ["/a", str(zip_path)]
    assert "à joindre" not in unquote(cmd[4])          # already attached


def test_empty_description_gets_a_placeholder():
    assert report.body("   ", "x.zip", True).startswith("(décrivez")


def test_diagnostic_strips_per_app_dictionaries():
    from voice_typer import diagnostic

    assert "app_dictionaries" in diagnostic.PRIVATE_FIELDS
