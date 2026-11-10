"""Desktop window: status, language picker and model manager (tkinter, no extra dependency)."""

import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from voice_typer import models
from voice_typer.app import Engine

COLORS = {
    "ready": "#2e9d4f",
    "recording": "#d93025",
    "busy": "#e8a317",
    "error": "#9e9e9e",
}


class Window:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.config = engine.config
        self.root = tk.Tk()
        self.root.title("Voice Typer")
        self.root.geometry("840x600")
        self.root.minsize(680, 520)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=26)
        self._build()
        self._refresh_models()

    # ---- layout -------------------------------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}
        root = self.root

        # Status
        status = ttk.Frame(root)
        status.pack(fill="x", **pad)
        self.dot = tk.Canvas(status, width=18, height=18, highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(2, 2, 16, 16, fill=COLORS["busy"], outline="")
        self.status_var = tk.StringVar(value="Starting…")
        ttk.Label(status, textvariable=self.status_var, font=("Segoe UI", 11, "bold")).pack(
            side="left", padx=8
        )
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=140)

        # Language
        lang = ttk.LabelFrame(root, text="Language you speak")
        lang.pack(fill="x", **pad)
        self.lang_codes = [code for code, _ in models.LANGUAGES]
        self.lang_combo = ttk.Combobox(
            lang, state="readonly", width=32, values=[name for _, name in models.LANGUAGES]
        )
        current = self.config.language if self.config.language in self.lang_codes else None
        self.lang_combo.current(self.lang_codes.index(current))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        self.lang_combo.pack(side="left", padx=10, pady=8)
        ttk.Label(
            lang,
            text="Choosing your language is faster and more accurate than auto-detect.",
            foreground="#666",
        ).pack(side="left", padx=4)

        # Models
        box = ttk.LabelFrame(root, text="AI model (speed vs. accuracy)")
        box.pack(fill="both", expand=True, **pad)
        cols = ("size", "speed", "accuracy", "status", "note")
        self.tree = ttk.Treeview(box, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Model")
        self.tree.column("#0", width=150, stretch=False)
        for col, title, width in [
            ("size", "Size", 70),
            ("speed", "Speed", 80),
            ("accuracy", "Accuracy", 80),
            ("status", "Status", 110),
            ("note", "Notes", 220),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, stretch=(col == "note"))
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.tree.bind("<Double-1>", lambda _e: self._use_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())

        buttons = ttk.Frame(box)
        buttons.pack(fill="x", padx=8, pady=(4, 8))
        self.use_btn = ttk.Button(buttons, text="Use this model", command=self._use_selected)
        self.use_btn.pack(side="left")
        ttk.Button(buttons, text="Import model folder…", command=self._import_folder).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="Add from Hugging Face…", command=self._import_hf).pack(
            side="left"
        )
        self.remove_btn = ttk.Button(buttons, text="Remove", command=self._remove_selected)
        self.remove_btn.pack(side="right")

        # Last transcript
        last = ttk.LabelFrame(root, text="Last dictation")
        last.pack(fill="x", **pad)
        self.last_var = tk.StringVar(value=f"Hold {self.config.hotkey} and speak.")
        ttk.Label(last, textvariable=self.last_var, wraplength=700).pack(
            anchor="w", padx=10, pady=8
        )

    # ---- helpers ------------------------------------------------------------------------
    def _set_status(self, text: str, color: str, busy: bool = False) -> None:
        self.status_var.set(text)
        self.dot.itemconfigure(self.dot_id, fill=COLORS[color])
        if busy:
            self.progress.pack(side="right")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _ready_text(self) -> str:
        return f"Ready — hold {self.config.hotkey} to dictate"

    def _label_for(self, source: str) -> str:
        for m in models.all_models(self.config.custom_models):
            if m.source == source:
                return m.label
        return source

    def _refresh_models(self) -> None:
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        active = self.engine.transcriber.source if self.engine.transcriber else None
        for m in models.all_models(self.config.custom_models):
            if m.source == self.engine.loading_source:
                status = "⏳ Loading…"
            elif m.source == active:
                status = "● In use"
            elif models.is_downloaded(m.source):
                status = "✓ Downloaded"
            else:
                status = "Not downloaded"
            self.tree.insert(
                "", "end", iid=m.source, text=m.label,
                values=(m.size, m.speed, m.accuracy, status, m.note),
            )
        keep = [s for s in selected if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)
        elif active and self.tree.exists(active):
            self.tree.selection_set(active)
        self._update_buttons()

    def _selected(self) -> models.ModelInfo | None:
        sel = self.tree.selection()
        if not sel:
            return None
        for m in models.all_models(self.config.custom_models):
            if m.source == sel[0]:
                return m
        return None

    def _update_buttons(self) -> None:
        m = self._selected()
        active = self.engine.transcriber.source if self.engine.transcriber else None
        busy = self.engine.loading_source is not None
        self.use_btn.state(["!disabled"] if m and not busy and m.source != active else ["disabled"])
        self.remove_btn.state(["!disabled"] if m and m.custom and m.source != active else ["disabled"])

    # ---- actions ------------------------------------------------------------------------
    def _on_language(self, _event=None) -> None:
        self.config.language = self.lang_codes[self.lang_combo.current()]
        self.config.save()

    def _use_selected(self) -> None:
        m = self._selected()
        if m is None or self.engine.loading_source is not None:
            return
        if not models.is_downloaded(m.source):
            size = f" ({m.size})" if m.size else ""
            if not messagebox.askyesno(
                "Download model",
                f"'{m.label}'{size} isn't on this PC yet.\n\n"
                "Download it now? This is the only step that needs the internet; "
                "afterwards it works offline.",
                parent=self.root,
            ):
                return
        self.engine.load_model(m.source)

    def _add_custom(self, label: str, source: str) -> None:
        if any(c["source"] == source for c in self.config.custom_models) or any(
            m.source == source for m in models.CATALOG
        ):
            messagebox.showinfo("Already added", f"'{label}' is already in the list.", parent=self.root)
            return
        self.config.custom_models.append({"label": label, "source": source})
        self.config.save()
        self._refresh_models()
        self.tree.selection_set(source)
        self.tree.see(source)

    def _import_folder(self) -> None:
        folder = filedialog.askdirectory(
            parent=self.root, title="Choose a faster-whisper (CTranslate2) model folder"
        )
        if not folder:
            return
        error = models.validate_folder(folder)
        if error:
            messagebox.showerror("Not a compatible model", error, parent=self.root)
            return
        self._add_custom(Path(folder).name, str(Path(folder)))

    def _import_hf(self) -> None:
        repo = simpledialog.askstring(
            "Add from Hugging Face",
            "Hugging Face repository of a faster-whisper (CTranslate2) model,\n"
            "for example:  Systran/faster-whisper-large-v3",
            parent=self.root,
        )
        if not repo:
            return
        repo = repo.strip().removeprefix("https://huggingface.co/").strip("/")
        if repo.count("/") != 1:
            messagebox.showerror(
                "Invalid name", "Use the form  owner/model-name", parent=self.root
            )
            return
        self._add_custom(repo.split("/")[1], repo)

    def _remove_selected(self) -> None:
        m = self._selected()
        if m is None or not m.custom:
            return
        if not messagebox.askyesno(
            "Remove model",
            f"Remove '{m.label}' from the list?\n\n(Files on disk are not deleted.)",
            parent=self.root,
        ):
            return
        self.config.custom_models = [c for c in self.config.custom_models if c["source"] != m.source]
        self.config.save()
        self._refresh_models()

    # ---- engine events ------------------------------------------------------------------
    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.engine.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _handle(self, kind: str, payload) -> None:
        if kind == "model_loading":
            label = self._label_for(payload)
            verb = "Loading" if models.is_downloaded(payload) else "Downloading"
            self._set_status(f"{verb} {label}…", "busy", busy=True)
            self._refresh_models()
        elif kind == "model_loaded":
            source, seconds = payload
            self._set_status(self._ready_text(), "ready")
            self.last_var.set(f"Model '{self._label_for(source)}' ready ({seconds:.1f}s).")
            self._refresh_models()
        elif kind == "model_error":
            source, err = payload
            self._refresh_models()
            if self.engine.transcriber:
                self._set_status(self._ready_text(), "ready")
            else:
                self._set_status("No model loaded", "error")
            messagebox.showerror(
                "Model error", f"Couldn't load '{self._label_for(source)}':\n\n{err}", parent=self.root
            )
        elif kind == "recording":
            self._set_status("● Recording… release to transcribe", "recording")
        elif kind == "transcribing":
            self._set_status("Transcribing…", "busy", busy=True)
        elif kind == "transcript":
            text, seconds = payload
            self._set_status(self._ready_text(), "ready")
            self.last_var.set(f"({seconds:.1f}s)  {text}" if text else "(nothing heard)")
        elif kind == "idle":
            self._set_status(self._ready_text(), "ready")
            if payload:
                self.last_var.set(str(payload))
        elif kind == "status":
            self.last_var.set(str(payload))

    # ---- lifecycle ----------------------------------------------------------------------
    def _quit(self) -> None:
        self.engine.stop()
        self.root.destroy()

    def run(self) -> None:
        self.engine.start()
        self.root.after(80, self._poll)
        self.root.mainloop()
