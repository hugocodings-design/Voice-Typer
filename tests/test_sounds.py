"""Start/stop sounds: a real faded tone played one at a time (winsound.Beep crackled after a while)."""

import io
import threading
import time
import wave

from voice_typer import sounds


def test_tone_is_a_short_wav_without_clicks():
    data = sounds.tone((880.0, 1175.0))
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
        frames = w.readframes(w.getnframes())
        assert 0.08 < w.getnframes() / 44100 < 0.15
    first = int.from_bytes(frames[:2], "little", signed=True)
    last = int.from_bytes(frames[-2:], "little", signed=True)
    assert abs(first) < 50 and abs(last) < 50                 # faded in and out: no click


def test_sounds_never_overlap_and_never_pile_up(monkeypatch):
    playing, overlaps, played = [0], [0], []
    lock = threading.Lock()

    def fake_play(data):
        with lock:
            playing[0] += 1
            overlaps[0] = max(overlaps[0], playing[0])
        time.sleep(0.05)
        with lock:
            playing[0] -= 1
        played.append(data)

    monkeypatch.setattr(sounds, "_play", fake_play)
    monkeypatch.setattr(sounds, "_worker", None)
    for _ in range(10):                                        # a burst of start/stop presses
        sounds.play(True)
        sounds.play(False)
    time.sleep(0.6)
    assert overlaps[0] == 1                                    # one at a time
    assert 1 <= len(played) <= 4                               # extra ones dropped, not queued forever


def test_a_broken_sound_device_never_raises(monkeypatch):
    def boom(data):
        raise RuntimeError("no device")

    monkeypatch.setattr(sounds, "_play", boom)
    monkeypatch.setattr(sounds, "_worker", None)
    sounds.play(True)
    time.sleep(0.1)
    sounds.play(False)                                         # the worker survived
    time.sleep(0.1)
    assert sounds._worker.is_alive()
