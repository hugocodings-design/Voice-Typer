"""0.9 features: undo the last dictation (« efface ça »), per-application dictionary, remembered microphone."""

import numpy as np
import pytest

from voice_typer import commands, dictionary, recorder, undo


# ------------------------------------------------------------------ « efface ça »
@pytest.mark.parametrize("text,lang", [("Efface ça.", "fr"), ("efface-ça !", "fr"), ("  Efface cela  ", None),
                                       ("Annule la dernière dictée.", "fr"), ("Delete that.", "en"),
                                       ("Scratch that", None)])
def test_undo_phrase_alone(text, lang):
    assert commands.is_undo(text, lang)


@pytest.mark.parametrize("text", ["Il faut que j'efface ça demain.", "Efface ça et recommence.", "",
                                  "Delete that file please"])
def test_undo_phrase_inside_a_sentence_is_just_text(text):
    assert not commands.is_undo(text, "fr") and not commands.is_undo(text, "en")


# ------------------------------------------------------------------ per-application dictionary
def test_app_dictionary_adds_words_and_wins_conflicts():
    general_v, general_r = ["Tailscale"], [{"from": "vt", "to": "Voice Typer"}, {"from": "mtl", "to": "Montréal"}]
    apps = [{"app": "outlook.exe", "vocabulary": ["Gagnon", "tailscale"],
             "replacements": [{"from": "mtl", "to": "MTL inc."}]}]
    v, r = dictionary.for_app(general_v, general_r, apps, "OUTLOOK.EXE")
    assert v == ["Tailscale", "Gagnon"]                      # no duplicate, general first
    assert dictionary.apply_replacements("vt à mtl", r) == "Voice Typer à MTL inc."
    v2, r2 = dictionary.for_app(general_v, general_r, apps, "winword.exe")   # other app: general only
    assert v2 == general_v and dictionary.apply_replacements("mtl", r2) == "Montréal"
    assert dictionary.for_app(general_v, general_r, apps, "")[0] == general_v


# ------------------------------------------------------------------ undo safety rules
class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def tracker(monkeypatch):
    monkeypatch.setattr(undo.UndoTracker, "_watch", lambda self: None)   # no real hooks in tests
    clock = Clock()
    return undo.UndoTracker(lambda: {57}, clock), clock    # 57 = scan code of our shortcut (Space)


def test_undo_once_in_same_window(tracker):
    t, _ = tracker
    assert t.take(1) == ("", "nothing")
    t.record("Bonjour Madame. ", hwnd=1)
    assert t.take(2) == ("", "other_window")
    assert t.take(1) == ("Bonjour Madame. ", None)
    assert t.take(1) == ("", "done")                        # never twice


def test_undo_refused_after_typing_or_clicking(tracker):
    t, _ = tracker
    t.record("abc ", hwnd=1)
    t.on_key("ctrl", 29)                                    # modifiers, our shortcut, Esc: harmless
    t.on_key("space", 57)
    t.on_key("esc", 1)
    t.on_key("x", 45, down=False)
    assert t.take(1)[1] is None
    t.record("abc ", hwnd=1)
    t.on_key("x", 45)
    assert t.take(1) == ("", "typed_since")
    t.record("abc ", hwnd=1)
    t._on_click()
    assert t.take(1) == ("", "clicked_since")


def test_our_own_typing_does_not_count(tracker):
    t, _ = tracker
    t.record("abc ", hwnd=1)
    t.suspend()
    t.on_key("backspace", 14)
    t.resume()
    assert t.take(1)[1] is None


def test_undo_expires(tracker):
    t, clock = tracker
    t.record("abc ", hwnd=1)
    clock.t += undo.UNDO_WINDOW_S + 1
    assert t.take(1) == ("", "too_old")


def test_char_count():
    assert undo.char_count("Bonjour,\r\nMerci 🙂 ") == len("Bonjour,\nMerci 🙂 ")


# ------------------------------------------------------------------ engine: dictate, then « efface ça »
class FakeTranscriber:
    source, device = "small", "cpu"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.hotwords = []

    def transcribe(self, audio, language=None, hotwords=None):
        self.hotwords.append(hotwords)
        return self.outputs.pop(0)


@pytest.fixture
def engine(monkeypatch, tmp_path):
    import keyboard

    from voice_typer import app, config as config_mod, output
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(undo.UndoTracker, "_watch", lambda self: None)
    monkeypatch.setattr(undo, "foreground_window", lambda: 42)
    screen = []

    def write(text, *a, **k):
        screen.append(text)

    def send(key, *a, **k):
        if key == "backspace":
            s = "".join(screen)[:-1]
            screen[:] = [s]

    monkeypatch.setattr(keyboard, "write", write)
    monkeypatch.setattr(keyboard, "send", send)
    monkeypatch.setattr(app, "send_text", lambda text, mode, trailing, keep: screen.append(
        text + (" " if trailing else "")))
    monkeypatch.setattr(output, "send_text", app.send_text)
    cfg = config_mod.Config()
    cfg.sounds = cfg.live_typing = cfg.live_preview = False
    eng = app.Engine(cfg)
    eng._wait_modifiers_released = lambda timeout=3.0: None
    return eng, screen


def _drain(eng):
    out = []
    while not eng.events.empty():
        out.append(eng.events.get())
    return out


def test_efface_ca_deletes_exactly_the_last_dictation(engine):
    eng, screen = engine
    eng.transcriber = FakeTranscriber(["Texte déjà là.", "Bonjour Madame.", "Efface ça."])
    audio = np.zeros(16000, dtype=np.float32)
    eng._transcribe_and_send(audio)
    eng._transcribe_and_send(audio)
    assert "".join(screen) == "Texte déjà là. Bonjour Madame. "
    eng._transcribe_and_send(audio)                              # said alone: nothing typed, undo instead
    assert "".join(screen) == "Texte déjà là. "
    assert ("undone", "Bonjour Madame. ") in _drain(eng)
    eng.transcriber.outputs.append("Efface ça.")
    eng._transcribe_and_send(audio)                              # only one undo: the first text stays
    assert "".join(screen) == "Texte déjà là. "
    assert ("undo_refused", "done") in _drain(eng)


def test_dictation_uses_the_app_dictionary(engine):
    eng, screen = engine
    eng.config.vocabulary = ["Tailscale"]
    eng.config.app_dictionaries = [{"app": "outlook.exe", "vocabulary": ["Gagnon"],
                                    "replacements": [{"from": "madame gagnon", "to": "Mme Gagnon"}]}]
    eng.transcriber = FakeTranscriber(["Bonjour madame Gagnon.", "Bonjour madame Gagnon."])
    eng._target_exe = "outlook.exe"
    eng._transcribe_and_send(np.zeros(16000, dtype=np.float32))
    eng._target_exe = "notepad.exe"
    eng._transcribe_and_send(np.zeros(16000, dtype=np.float32))
    assert eng.transcriber.hotwords == ["Tailscale, Gagnon", "Tailscale"]
    assert "".join(screen) == "Bonjour Mme Gagnon. Bonjour madame Gagnon. "


# ------------------------------------------------------------------ remembered microphone
class FakeStream:
    def __init__(self, device=None, **kw):
        self.device = device

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


def test_microphone_falls_back_then_comes_back(monkeypatch, engine):
    eng, _ = engine
    present = {"on": False}
    monkeypatch.setattr(recorder.sd, "InputStream", FakeStream)
    monkeypatch.setattr(recorder, "_find", lambda name: 7 if present["on"] else None)
    refreshes = []
    monkeypatch.setattr(recorder, "refresh_devices", lambda min_interval=5.0: refreshes.append(1) or True)
    eng.config.input_device = "Casque Jabra"
    eng.recorder.device_name = "Casque Jabra"

    eng.recorder.start()                       # unplugged: Windows default, and the user is told
    assert eng.recorder._stream.device is None and eng.recorder.using_fallback and refreshes
    assert recorder._open_streams == 1
    eng._check_microphone()
    eng.recorder.stop()
    assert recorder._open_streams == 0
    assert ("mic_fallback", "Casque Jabra") in _drain(eng)
    assert eng.config.input_device == "Casque Jabra"     # the choice is kept

    present["on"] = True                       # plugged back in: used again by itself
    eng.recorder.start()
    assert eng.recorder._stream.device == 7 and not eng.recorder.using_fallback
    eng._check_microphone()
    eng.recorder.stop()
    assert ("mic_back", "Casque Jabra") in _drain(eng)


def test_device_rescan_waits_while_recording(monkeypatch):
    calls = []
    monkeypatch.setattr(recorder.sd, "_terminate", lambda: calls.append("t"))
    monkeypatch.setattr(recorder.sd, "_initialize", lambda: calls.append("i"))
    monkeypatch.setattr(recorder, "_last_refresh", 0.0)
    monkeypatch.setattr(recorder, "_open_streams", 1)
    assert not recorder.refresh_devices(0) and calls == []
    monkeypatch.setattr(recorder, "_open_streams", 0)
    assert recorder.refresh_devices(0) and calls == ["t", "i"]


def test_model_symlinks_become_real_files(tmp_path):
    import os

    import pytest

    from voice_typer import models

    blob = tmp_path / "blobs" / "ab"
    blob.mkdir(parents=True)
    (blob / "data").write_bytes(b"weights")
    snap = tmp_path / "snap"
    snap.mkdir()
    try:
        os.symlink(blob / "data", snap / "model.bin")
    except OSError:
        pytest.skip("symlinks not allowed on this PC")
    models.unlink_symlinks(snap)
    assert not (snap / "model.bin").is_symlink()
    assert (snap / "model.bin").read_bytes() == b"weights"


class _FakeRecorder:
    def __init__(self):
        self.is_recording = False
        self.device_name = None
        self.using_fallback = False

    def start(self):
        self.is_recording = True

    def stop(self):
        self.is_recording = False
        return np.zeros(10, dtype=np.float32)  # too short: nothing transcribed


@pytest.fixture
def keyed(engine, monkeypatch):
    """Engine whose recorder is fake and whose clock is driven by the test."""
    eng, _ = engine
    from voice_typer import app

    eng.recorder = _FakeRecorder()
    eng.transcriber = FakeTranscriber([])
    now = [100.0]
    monkeypatch.setattr(app.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(app.Engine, "_arm_escape", lambda self: None)
    monkeypatch.setattr(app.Engine, "_safety_stop", lambda self, started: None)
    return eng, now


@pytest.mark.parametrize("mode, hold_s, after_release", [
    ("hold", 0.1, False), ("hold", 2.0, False),
    ("toggle", 0.1, True), ("toggle", 2.0, True),
    ("auto", 0.1, True),    # quick tap: keeps listening
    ("auto", 2.0, False),   # held while speaking: release ends it
])
def test_hotkey_modes(keyed, mode, hold_s, after_release):
    eng, now = keyed
    eng.config.mode = mode
    eng._on_down(None)
    assert eng.recorder.is_recording
    now[0] += hold_s
    eng._on_up(None)
    assert eng.recorder.is_recording is after_release
    if after_release:  # second press stops it, and its release doesn't restart anything
        now[0] += 3.0
        eng._on_down(None)
        assert not eng.recorder.is_recording
        now[0] += 1.0
        eng._on_up(None)
        assert not eng.recorder.is_recording


def test_auto_mode_ignores_release_of_another_key(keyed):
    eng, now = keyed
    eng.config.mode = "auto"
    eng._on_down(None)
    now[0] += 2.0
    eng._on_up("email")  # a preset key released meanwhile
    assert eng.recorder.is_recording


def test_shortcut_without_model_reports_it(keyed):
    eng, _ = keyed
    eng.transcriber = None
    _drain(eng)
    eng._on_down(None)
    assert not eng.recorder.is_recording
    assert ("status", "no_model") in _drain(eng)
