import sys
import threading
import time

import pytest

from voice_typer import config as config_mod, instance


def test_only_our_own_executable_can_be_closed(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Users\x\AppData\Local\Programs\Voice Typer\Voice Typer.exe")
    assert instance.is_our_executable("voice typer.exe")
    assert not instance.is_our_executable("chrome.exe")
    monkeypatch.setattr(sys, "frozen", False)
    assert instance.is_our_executable("pythonw.exe")
    assert not instance.is_our_executable("notepad.exe")


def test_close_choice_is_a_portable_setting():
    from voice_typer.transfer import PORTABLE

    assert config_mod.Config().close_action == "ask"
    assert "close_action" in PORTABLE


@pytest.mark.skipif(sys.platform != "win32", reason="named Windows events")
def test_second_launch_brings_the_running_copy_forward(monkeypatch, tmp_path):
    suffix = str(time.monotonic_ns())
    monkeypatch.setattr(instance, "SHOW_EVENT", "VoiceTyper.Test.Show." + suffix)
    monkeypatch.setattr(instance, "ACK_EVENT", "VoiceTyper.Test.Ack." + suffix)
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)

    assert instance.ask_existing_to_show(timeout=0.3) is False   # nobody running yet

    shown = threading.Event()

    def on_show(ack):          # what the window does: show itself, then confirm
        shown.set()
        ack()

    instance.wait_for_launches(on_show)
    assert (tmp_path / "instance.pid").read_text().strip().isdigit()
    assert instance.ask_existing_to_show(timeout=3.0) is True
    assert shown.is_set()


@pytest.mark.skipif(sys.platform != "win32", reason="named Windows events")
def test_frozen_copy_does_not_answer(monkeypatch, tmp_path):
    suffix = str(time.monotonic_ns())
    monkeypatch.setattr(instance, "SHOW_EVENT", "VoiceTyper.Test.Show." + suffix)
    monkeypatch.setattr(instance, "ACK_EVENT", "VoiceTyper.Test.Ack." + suffix)
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    instance.wait_for_launches(lambda ack: None)               # interface frozen: never confirms
    t0 = time.monotonic()
    assert instance.ask_existing_to_show(timeout=0.5) is False
    assert time.monotonic() - t0 < 2.0
