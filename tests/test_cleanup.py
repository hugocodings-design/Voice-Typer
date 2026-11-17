from voice_typer.cleanup import remove_fillers, strip_hallucinations


def test_hallucinations_removed():
    assert strip_hallucinations("Sous-titrage Société Radio-Canada") == ""
    assert strip_hallucinations(" [BLANK_AUDIO] ") == ""
    assert strip_hallucinations("Bonjour Marc [Musique]") == "Bonjour Marc"
    assert strip_hallucinations("Sous-titres réalisés par la communauté d'Amara.org") == ""
    assert strip_hallucinations("Merci pour le rapport.") == "Merci pour le rapport."


def test_fillers_and_repeats():
    assert remove_fillers("euh je pense que le le projet euh avance", "fr") == "je pense que le projet avance"
    assert remove_fillers("Euh, je pense que oui.", "fr") == "Je pense que oui."
    assert remove_fillers("um I think uh so", "en") == "I think so"
    assert remove_fillers("Euh I think so", None) == "I think so"


def test_fillers_keep_real_words():
    assert remove_fillers("Heureux de vous voir", "fr") == "Heureux de vous voir"
    assert remove_fillers("nous nous voyons demain", "fr") == "nous nous voyons demain"
    assert remove_fillers("Humour et bahut", "fr") == "Humour et bahut"


def test_suggested_app_presets_skip_taken_apps_and_missing_presets():
    from voice_typer.config import suggest_app_presets

    existing = [{"app": "Outlook.exe", "preset": "fix"}]
    new = suggest_app_presets(existing, {"email", "message"})
    apps = {r["app"]: r["preset"] for r in new}
    assert "outlook.exe" not in apps            # the user's own rule wins
    assert apps["olk.exe"] == "email"
    assert apps["ms-teams.exe"] == "message"
    assert "onenote.exe" not in apps            # no "notes" preset: not suggested
    assert suggest_app_presets(existing + new, {"email", "message"}) == []


def test_new_settings_travel_but_button_position_stays():
    from voice_typer.config import Config
    from voice_typer.transfer import PORTABLE

    cfg = Config()
    assert cfg.remove_fillers is True and cfg.mic_button is True and cfg.mic_button_pos is None
    assert "remove_fillers" in PORTABLE and "mic_button" in PORTABLE
    assert "mic_button_pos" not in PORTABLE     # screen layout differs between PCs
