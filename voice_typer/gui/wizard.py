"""Welcome assistant shown on first launch (and from Réglages): language, models, microphone, shortcut."""

import tkinter as tk
from tkinter import ttk

from voice_typer import models, ui_theme, writer
from voice_typer.gui.common import UI_LANGUAGES
from voice_typer.recorder import Recorder, list_microphones

STEPS = ["welcome", "speak", "models", "mic", "shortcut", "done"]

FR_TURBO = "Zoont/faster-whisper-large-v3-turbo-int8-ct2"
FR_GPU = "bofenghuang/whisper-large-v3-french-distil-dec16#ctranslate2"
EN_GPU = "distil-large-v3.5"


def speech_choices(speak: str, cuda: bool) -> list[tuple[str, str]]:
    """[(model source, tag key)] — first one is the recommendation for this language/hardware."""
    if speak == "en":
        return ([(EN_GPU, "wz_tag_best"), ("distil-small.en", "wz_tag_fast")] if cuda
                else [("distil-medium.en", "wz_tag_balanced"), ("distil-small.en", "wz_tag_fast")])
    if speak == "fr":
        return ([(FR_GPU, "wz_tag_best"), (FR_TURBO, "wz_tag_balanced")] if cuda
                else [(FR_TURBO, "wz_tag_balanced"), ("small", "wz_tag_fast")])
    return ([(FR_TURBO, "wz_tag_best"), ("large-v3-turbo", "wz_tag_precise")] if cuda
            else [(FR_TURBO, "wz_tag_balanced"), ("small", "wz_tag_fast")])


def writing_choice(cuda: bool) -> writer.LlmInfo:
    return writer.LLM_CATALOG[1] if cuda else writer.LLM_CATALOG[0]


class WelcomeWizard:
    _wizard: tk.Toplevel | None = None

    def _open_wizard(self, force: bool = False, on_close=None) -> None:
        if self._wizard is not None:
            self._wizard.lift()
            return
        self._wz_on_close = on_close
        self._wz_step = 0
        lang = self.config.language
        self._wz = {
            "speak": "fr" if lang == "fr" else "en" if lang == "en" else "both",
            "speech": None, "writing": not self.config.first_run_done or bool(self.engine.writer),
        }
        dlg = self._wizard = tk.Toplevel(self.root)
        dlg.title(self.t("wz_title"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.protocol("WM_DELETE_WINDOW", lambda: self._wizard_finish(apply=False))
        dlg.geometry("760x560")
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - 760) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - 560) // 3
        dlg.geometry(f"760x560+{max(x, 0)}+{max(y, 0)}")
        self._wizard_restyle()
        dlg.focus_force()

    # ---- frame / navigation
    def _wizard_restyle(self) -> None:
        dlg = self._wizard
        pal = self.pal
        dlg.configure(bg=pal["bg"])
        ui_theme._dark_title_bar(dlg, self.mode == "dark")  # noqa: SLF001
        for w in dlg.winfo_children():
            w.destroy()
        self._wz_stop_mic()

        head = tk.Frame(dlg, bg=pal["sidebar"], height=64)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=ui_theme.ICONS["mic"], font=(self.fonts.icon[0], 18), bg=pal["sidebar"],
                 fg=pal["accent"]).pack(side="left", padx=(24, 10))
        tk.Label(head, text="Voice Typer", font=self.fonts.app, bg=pal["sidebar"], fg=pal["text"]).pack(side="left")
        dots = tk.Frame(head, bg=pal["sidebar"])
        dots.pack(side="right", padx=24)
        for i in range(len(STEPS)):
            color = pal["accent"] if i <= self._wz_step else pal["border"]
            c = tk.Canvas(dots, width=26 if i == self._wz_step else 10, height=10, bg=pal["sidebar"],
                          highlightthickness=0)
            c.pack(side="left", padx=3)
            w = 26 if i == self._wz_step else 10
            c.create_oval(0, 0, 10, 10, fill=color, outline="")
            if w > 10:
                c.create_oval(w - 10, 0, w, 10, fill=color, outline="")
                c.create_rectangle(5, 0, w - 5, 10, fill=color, outline="")

        foot = ttk.Frame(dlg, padding=(28, 12, 28, 20))
        foot.pack(side="bottom", fill="x")
        last = self._wz_step == len(STEPS) - 1
        ttk.Button(foot, text=self.t("wz_finish") if last else self.t("wz_next"), style="Accent.TButton",
                   command=self._wizard_next).pack(side="right")
        if self._wz_step > 0:
            ttk.Button(foot, text=self.t("wz_back"), command=self._wizard_back).pack(side="right", padx=8)
        if not last:
            skip = ttk.Label(foot, text=self.t("wz_skip"), style="Muted.TLabel", cursor="hand2")
            skip.pack(side="left")
            skip.bind("<Button-1>", lambda _e: self._wizard_finish(apply=True))
        ttk.Label(foot, text=self.t("wz_step", n=self._wz_step + 1, total=len(STEPS)),
                  style="Muted.TLabel").pack(side="left", padx=(16, 0))

        body = ttk.Frame(dlg, padding=(36, 26, 36, 0))
        body.pack(fill="both", expand=True)
        getattr(self, f"_wz_{STEPS[self._wz_step]}")(body)

    def _wz_header(self, body, title: str, sub: str) -> None:
        ttk.Label(body, text=title, font=self.fonts.h1).pack(anchor="w")
        ttk.Label(body, text=sub, style="Muted.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(4, 20))

    def _wizard_next(self) -> None:
        if self._wz_step == len(STEPS) - 1:
            self._wizard_finish(apply=True)
            return
        self._wz_step += 1
        self._wizard_restyle()

    def _wizard_back(self) -> None:
        self._wz_step = max(0, self._wz_step - 1)
        self._wizard_restyle()

    # ---- steps
    def _wz_welcome(self, body) -> None:
        self._wz_header(body, self.t("wz_welcome_title"), self.t("wz_welcome_sub"))
        for key in ("wz_welcome_1", "wz_welcome_2", "wz_welcome_3", "wz_welcome_4"):
            row = ttk.Frame(body)
            row.pack(anchor="w", pady=5)
            ttk.Label(row, text="✓", foreground=self.pal["ok"], font=self.fonts.bold).pack(side="left", padx=(0, 10))
            ttk.Label(row, text=self.t(key), wraplength=640, justify="left").pack(side="left")
        row = ttk.Frame(body)
        row.pack(anchor="w", pady=(26, 0))
        ttk.Label(row, text=self.t("set_ui_lang")).pack(side="left")
        combo = ttk.Combobox(row, state="readonly", width=16, values=[n for _, n in UI_LANGUAGES])
        codes = [c for c, _ in UI_LANGUAGES]
        combo.current(codes.index(self.config.ui_language) if self.config.ui_language in codes else 0)

        def changed(_e=None):
            self.config.ui_language = codes[combo.current()]
            self.config.save()
            self._wizard.title(self.t("wz_title"))
            self._build()  # rebuilds the main window, then the assistant (see _build)

        combo.bind("<<ComboboxSelected>>", changed)
        combo.pack(side="left", padx=12)

    def _wz_speak(self, body) -> None:
        self._wz_header(body, self.t("wz_speak_title"), self.t("wz_speak_sub"))
        var = tk.StringVar(value=self._wz["speak"])

        def pick():
            self._wz["speak"] = var.get()
            self._wz["speech"] = None  # recompute the recommendation

        for value, key in (("fr", "wz_speak_fr"), ("en", "wz_speak_en"), ("both", "wz_speak_both")):
            ttk.Radiobutton(body, text=self.t(key), value=value, variable=var, command=pick).pack(anchor="w", pady=6)

    def _wz_models(self, body) -> None:
        cuda = self._cuda
        self._wz_header(body, self.t("wz_models_title"),
                        self.t("wz_hw_gpu", name=self._gpu_name or "NVIDIA") if cuda else self.t("wz_hw_cpu"))
        choices = speech_choices(self._wz["speak"], cuda)
        if self._wz["speech"] not in [s for s, _ in choices]:
            self._wz["speech"] = choices[0][0]
        info = {m.source: m for m in models.all_models([])}
        var = tk.StringVar(value=self._wz["speech"])
        ttk.Label(body, text=self.t("wz_speech_model"), font=self.fonts.bold).pack(anchor="w", pady=(0, 6))
        for i, (src, tag) in enumerate(choices):
            m = info[src]
            done = " ✓ " + self.t("wz_on_pc") if models.is_downloaded(src) else ""
            label = f"{m.label}  —  {self.t(tag)}  ·  {m.size}{done}"
            if i == 0:
                label += "   ★ " + self.t("wz_recommended")
            ttk.Radiobutton(body, text=label, value=src, variable=var,
                            command=lambda: self._wz.__setitem__("speech", var.get())).pack(anchor="w", pady=4)

        llm = writing_choice(cuda)
        ttk.Label(body, text=self.t("wz_writing_title"), font=self.fonts.bold).pack(anchor="w", pady=(22, 6))
        wvar = tk.BooleanVar(value=self._wz["writing"])
        done = " ✓ " + self.t("wz_on_pc") if writer.is_downloaded(llm.source) else ""
        ttk.Checkbutton(body, text=self.t("wz_writing_check", name=llm.label, size=llm.size) + done,
                        style="Switch.TCheckbutton", variable=wvar,
                        command=lambda: self._wz.__setitem__("writing", wvar.get())).pack(anchor="w")
        ttk.Label(body, text=self.t("wz_models_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(18, 0))

    def _wz_mic(self, body) -> None:
        self._wz_header(body, self.t("wz_mic_title"), self.t("wz_mic_sub"))
        mics = [None] + list_microphones()
        names = [self.t("mic_default")] + mics[1:]
        combo = ttk.Combobox(body, state="readonly", width=60, values=names)
        cur = self.config.input_device if self.config.input_device in mics else None
        combo.current(mics.index(cur))
        combo.pack(anchor="w")

        def changed(_e=None):
            self.config.input_device = mics[combo.current()]
            self.config.save()
            self._wz_stop_mic()
            self._wz_start_mic()

        combo.bind("<<ComboboxSelected>>", changed)
        ttk.Label(body, text=self.t("wz_mic_speak"), style="Muted.TLabel").pack(anchor="w", pady=(22, 6))
        self._wz_meter = ttk.Progressbar(body, mode="determinate", maximum=100, length=420)
        self._wz_meter.pack(anchor="w")
        self._wz_start_mic()

    def _wz_start_mic(self) -> None:
        rec = Recorder(self.config.sample_rate)
        rec.device_name = self.config.input_device
        try:
            rec.start()
        except Exception:  # noqa: BLE001 — shown as an empty meter
            return
        self._wz_rec = rec
        self._wz_tick()

    def _wz_tick(self) -> None:
        rec = getattr(self, "_wz_rec", None)
        if rec is None:
            return
        try:
            self._wz_meter["value"] = min(100, rec.level * 1200)
        except tk.TclError:
            self._wz_stop_mic()
            return
        self.root.after(60, self._wz_tick)

    def _wz_stop_mic(self) -> None:
        rec = getattr(self, "_wz_rec", None)
        self._wz_rec = None
        if rec is not None:
            rec.stop()

    def _wz_shortcut(self, body) -> None:
        self._wz_header(body, self.t("wz_key_title"), self.t("wz_key_sub"))
        row = ttk.Frame(body)
        row.pack(anchor="w")
        self._keycaps(row, self.config.hotkey).pack(side="left")
        ttk.Button(row, text=self.t("change"), command=lambda: self._record_hotkey("main")).pack(side="left", padx=14)
        var = tk.StringVar(value=self.config.mode)

        def mode():
            self.config.mode = var.get()
            self.config.save()

        for value, key in (("hold", "mode_hold"), ("toggle", "mode_toggle")):
            ttk.Radiobutton(body, text=self.t(key), value=value, variable=var, command=mode).pack(
                anchor="w", pady=(16 if value == "hold" else 4, 0))
        ttk.Label(body, text=self.t("wz_key_tips"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(20, 0))

    def _wz_done(self, body) -> None:
        self._wz_header(body, self.t("wz_done_title"), self.t("wz_done_sub"))
        info = {m.source: m for m in models.all_models([])}
        m = info.get(self._wz["speech"] or self.config.model)
        rows = [(self.t("wz_sum_speech"), m.label if m else self.config.model),
                (self.t("wz_sum_writing"), writing_choice(self._cuda).label if self._wz["writing"] else self.t("none")),
                (self.t("wz_sum_key"), self._hotkey_label()),
                (self.t("wz_sum_presets"), ", ".join(f"{self._hotkey_label(p['hotkey'])} {p['name']}"
                                                     for p in self.config.presets or [] if p.get("hotkey")))]
        grid = ttk.Frame(body)
        grid.pack(anchor="w")
        for i, (k, v) in enumerate(rows):
            ttk.Label(grid, text=k, style="Muted.TLabel").grid(row=i, column=0, sticky="w", pady=4)
            ttk.Label(grid, text=v, font=self.fonts.bold).grid(row=i, column=1, sticky="w", padx=18, pady=4)
        ttk.Label(body, text=self.t("wz_done_try", hotkey=self._hotkey_label()), wraplength=680,
                  justify="left").pack(anchor="w", pady=(22, 0))

    # ---- finish
    def _wizard_finish(self, apply: bool) -> None:
        self._wz_stop_mic()
        if apply:
            speak = self._wz["speak"]
            self.config.language = None if speak == "both" else speak
            favs = {"fr": ["fr", "en"], "en": ["en", "fr"], "both": ["fr", "en"]}[speak]
            self.config.favorite_languages = favs + [c for c in self.config.favorite_languages if c not in favs]
            if not self._wz["speech"]:
                self._wz["speech"] = speech_choices(speak, self._cuda)[0][0]
            if self._wz["writing"]:
                self.config.writing_model = writing_choice(self._cuda).source
        self.config.first_run_done = True
        speech = self._wz["speech"] if apply else None
        self.config.save()
        dlg, self._wizard = self._wizard, None
        dlg.destroy()
        on_close, self._wz_on_close = self._wz_on_close, None
        if speech:
            self.config.model = speech
        if on_close:  # first launch: the engine starts now, with the chosen model
            on_close()
        elif speech and (self.engine.transcriber is None or self.engine.transcriber.source != speech):
            self.engine.load_model(speech)
        if apply and self._wz["writing"]:
            self.engine.load_writer()
        self._build()
