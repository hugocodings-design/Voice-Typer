from voice_typer import speed


def test_threads_count_physical_cores():
    assert speed.cpu_threads(False, 16) == 0          # off: CTranslate2's own default (4)
    assert speed.cpu_threads(True, 16) == 8           # 8 cores / 16 threads
    assert speed.cpu_threads(True, 8) == 4
    assert speed.cpu_threads(True, 6) == 6            # no hyper-threading reported
    assert speed.cpu_threads(True, 2) == 4            # never below the default


def test_modes():
    assert speed.decode_options("auto", "cpu")["beam_size"] == 1
    assert speed.decode_options("auto", "cuda") == {"beam_size": 5}
    assert speed.decode_options("accurate", "cpu") == {"beam_size": 5}
    fast = speed.decode_options("fast", "cuda")
    assert fast["beam_size"] == 1 and fast["without_timestamps"] and not fast["condition_on_previous_text"]
    assert speed.effective_mode("nonsense", "cpu") == "fast"


def test_timing_line_shows_only_steps_that_ran():
    t = {"audio": 6.04, "transcribe": 1.23, "rewrite": 2.6, "subject": 0.31, "paste": 0.01}
    assert speed.format_timings(t, "fr") == "audio 6,0 s · transcription 1,2 s · IA 2,6 s · objet 0,3 s"
    assert speed.format_timings({"audio": 2.0, "transcribe": 0.5}, "en") == "audio 2.0 s · transcription 0.5 s"
    assert speed.format_timings({}, "fr") == ""


def test_settings_validation_and_portability(tmp_path, monkeypatch):
    import json

    from voice_typer import config as config_mod
    from voice_typer.transfer import PORTABLE

    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    (tmp_path / "settings.json").write_text(json.dumps({"speed_mode": "turbo", "first_run_done": True}))
    cfg = config_mod.Config.load()
    assert cfg.speed_mode == "auto" and cfg.all_cores is True
    assert {"speed_mode", "all_cores"} <= set(PORTABLE)


def test_timings_say_which_steps_ran_at_home():
    from voice_typer.speed import format_timings

    t = {"audio": 4.0, "transcribe": 0.6, "rewrite": 1.8, "home": 1.0, "home_ai": 1.0}
    assert format_timings(t, "fr") == "audio 4,0 s · transcription 0,6 s (maison) · IA 1,8 s (maison)"
    assert format_timings({**t, "home_ai": None}, "en") == "audio 4.0 s · transcription 0.6 s (home) · AI 1.8 s"


def test_timings_split_home_pc_and_network():
    from voice_typer.speed import format_timings

    t = {"audio": 9.5, "transcribe": 6.1, "home": 1.0, "home_compute": 0.8,
         "rewrite": 2.2, "home_ai": 1.0, "home_ai_net": 0.5}
    assert format_timings(t, "fr") == ("audio 9,5 s · transcription 6,1 s (maison : 0,8 s + réseau 5,3 s) · "
                                       "IA 2,2 s (maison, + réseau 0,5 s)")
    assert "(home: 0.8 s + network 5.3 s)" in format_timings(t, "en")
