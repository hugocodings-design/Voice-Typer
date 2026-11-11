"""Fast unit tests (no microphone, no model download, no GPU). Run: python -m pytest"""

import json

import pytest

from voice_typer import config as config_mod
from voice_typer import dictionary, hotkey, languages
from voice_typer.i18n import STRINGS, pretty_hotkey
from voice_typer.writer import _fix_invented_greeting, default_presets


# ---- dictionary -------------------------------------------------------------------------
def test_replacements_are_case_insensitive_whole_phrases():
    repl = [{"from": "chat GPT", "to": "ChatGPT"}]
    assert dictionary.apply_replacements("j'utilise chat gpt et Chat GPT.", repl) == "j'utilise ChatGPT et ChatGPT."
    assert dictionary.apply_replacements("chatgptx", repl) == "chatgptx"


def test_hotwords_joined():
    assert dictionary.hotwords(["Hugo", "Speechify"]) == "Hugo, Speechify"
    assert not dictionary.hotwords([])


# ---- hotkeys ----------------------------------------------------------------------------
@pytest.mark.parametrize("combo,expected", [
    ("ctrl+alt+space", None), ("f9", None), ("right ctrl", None),
    ("a", "single"), ("space", "single"), ("", "empty"), ("ctrl+nonexistentkey", "unknown"),
])
def test_validate(combo, expected):
    assert hotkey.validate(combo) == expected


def test_normalize_and_pretty():
    assert hotkey.normalize(" Ctrl + Alt+Space ") == ["ctrl", "alt", "space"]
    assert pretty_hotkey("fr", "ctrl+shift+v") == "Ctrl + Maj + V"


# ---- settings ---------------------------------------------------------------------------
@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "SETTINGS_FILE", f)
    return f


def test_defaults_when_missing(settings_file):
    cfg = config_mod.Config.load()
    assert cfg.ui_language == "fr" and cfg.presets and cfg.settings_version == 3


def test_v1_cpu_migrates_to_auto(settings_file):
    settings_file.write_text(json.dumps({"device": "cpu", "settings_version": 1}))
    assert config_mod.Config.load().device == "auto"


def test_default_presets_skip_taken_hotkeys(settings_file):
    settings_file.write_text(json.dumps({"hotkey": "f2", "settings_version": 3}))
    cfg = config_mod.Config.load()
    email = next(p for p in cfg.presets if p["id"] == "email")
    assert email["hotkey"] == ""


def test_v2_presets_refreshed_keeping_user_hotkeys(settings_file):
    old = [{"id": "email", "name": "Mon courriel", "hotkey": "f7", "instructions": "old"},
           {"id": "mine", "name": "Perso", "hotkey": "", "instructions": "custom"}]
    settings_file.write_text(json.dumps({"presets": old, "settings_version": 2}))
    cfg = config_mod.Config.load()
    email, mine = cfg.presets
    assert email["hotkey"] == "f7" and email["name"] == "Mon courriel" and email["instructions"] != "old"
    assert mine["instructions"] == "custom"


def test_save_roundtrip_keeps_accents(settings_file):
    cfg = config_mod.Config.load()
    cfg.signature = "Hugo — Responsable des achats"
    cfg.save()
    assert "Responsable des achats" in settings_file.read_text(encoding="utf-8")
    assert config_mod.Config.load().signature == cfg.signature


def test_unknown_keys_ignored(settings_file):
    settings_file.write_text(json.dumps({"bogus": 1, "model": "tiny"}))
    assert config_mod.Config.load().model == "tiny"


# ---- AI writing guard -------------------------------------------------------------------
@pytest.mark.parametrize("out,src,expected", [
    ("Bonjour Monsieur Y,\n\nTexte", "le bureau ferme", "Bonjour,\n\nTexte"),
    ("Bonjour Monsieur Tremblay,\nx", "courriel à monsieur tremblay", "Bonjour Monsieur Tremblay,\nx"),
    ("Salut Marc, je suis en retard", "dis à Marc", "Salut Marc, je suis en retard"),
    ("Bonjour, Julie Martin,\nx", "écris à Julie Martin", "Bonjour Julie Martin,\nx"),
    ("Hello Ms. Smith,\nx", "email to John", "Hello,\nx"),
    ("Bonjour,\n\nJe voulais, merci", "y", "Bonjour,\n\nJe voulais, merci"),
])
def test_invented_greeting_guard(out, src, expected):
    assert _fix_invented_greeting(out, src) == expected


@pytest.mark.parametrize("ui", ["fr", "en"])
def test_default_presets_shape(ui):
    presets = default_presets(ui)
    assert {p["id"] for p in presets} == {"email", "message", "notes", "fix"}
    assert "{signature}" in next(p for p in presets if p["id"] == "email")["instructions"]


# ---- i18n / languages -------------------------------------------------------------------
def test_fr_and_en_have_same_keys():
    assert set(STRINGS["fr"]) == set(STRINGS["en"])


def test_language_names():
    assert languages.name(None, "fr") == "Détection automatique"
    assert languages.name("fr", "en") == "French"


def test_retry_while_locked(monkeypatch):
    import time

    from voice_typer import models

    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = []

    def load():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("Unable to open file 'model.bin' in model 'x'")
        return "ok"

    assert models.retry_while_locked(load) == "ok" and len(calls) == 3

    def broken():
        raise RuntimeError("CUDA failed")

    import pytest

    with pytest.raises(RuntimeError, match="CUDA"):
        models.retry_while_locked(broken)


# ---- live typing (streaming.py) ----------------------------------------------------------
def test_live_typer_types_only_confirmed_words_and_fixes_the_end():
    from voice_typer.streaming import LiveTyper

    t = LiveTyper()
    assert t.update("Bonjour je") == ""              # first pass: nothing confirmed yet
    assert t.update("Bonjour je suis") == "Bonjour je"
    assert t.update("Bonjour je suis allé") == " suis"
    assert t.update("Bonjour, je suis allé au") == ""  # an earlier word changed: never take back
    assert t.typed == "Bonjour je suis"
    back, rest = t.finish("Bonjour, je suis allé au marché. ")
    screen = t.typed[:len(t.typed) - back] + rest
    assert screen == "Bonjour, je suis allé au marché. " and back == len("Bonjour je suis") - len("Bonjour")


def test_live_typer_nothing_typed():
    from voice_typer.streaming import LiveTyper

    assert LiveTyper().finish("Salut ") == (0, "Salut ")
