"""Voice Typer Home as a small app next to the clock (no black window to close by accident).

- tray icon (blue microphone) with: what is loaded and where (graphics card / processor), « Copier la clé »,
  « Ouvrir le journal », « Démarrer avec Windows », « Quitter »;
- a Windows notification when a model can't be loaded, or lands on the processor (slow: graphics card full);
- a journal %APPDATA%\\VoiceTyperHome\\home.log with the same short lines (never audio or text);
- one copy at a time (named mutex): a second start just says it is already running.
"""

import logging
import logging.handlers
import os
import sys
import threading
import time
from pathlib import Path

from home_server.server import Models, home_dir, load_or_create_key, make_server

MUTEX_NAME = "VoiceTyperHome.SingleInstance"
RUN_VALUE = "VoiceTyperHome"
BLUE = "#2563eb"
LABELS = {"whisper": "Whisper", "writer": "IA d'écriture"}


def setup_log(folder: Path | None = None) -> logging.Logger:
    folder = folder or home_dir()
    folder.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("voice_typer_home")
    if not log.handlers:
        handler = logging.handlers.RotatingFileHandler(folder / "home.log", maxBytes=300_000, backupCount=1,
                                                       encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def status_lines(status: dict) -> list[str]:
    """Menu lines: « Whisper : small — carte graphique » / « IA d'écriture : chargement de … »."""
    out = []
    for kind in ("whisper", "writer"):
        name, device, loading = status.get(kind, ("", "", None))
        if loading:
            out.append(f"{LABELS[kind]} : chargement de {short(loading)}…")
        elif name:
            where = "carte graphique" if device == "cuda" else "PROCESSEUR (lent)"
            out.append(f"{LABELS[kind]} : {short(name)} — {where}")
        else:
            out.append(f"{LABELS[kind]} : pas encore chargé")
    return out


def short(source: str) -> str:
    return source.split("/")[-1].split("#")[0].replace("-ct2-int8", "")


def load_message(kind: str, source: str, device: str, error: str) -> str | None:
    """Notification text after a load, or None when all is well."""
    if error:
        return f"{LABELS[kind]} « {short(source)} » impossible à charger. Le modèle de ce PC est utilisé."
    if device and device != "cuda":
        return (f"{LABELS[kind]} « {short(source)} » tourne sur le processeur : la carte graphique est pleine. "
                "Fermez Voice Typer sur ce PC ou choisissez un modèle plus léger.")
    return None


def autostart_command(root: Path | None = None) -> str:
    root = root or Path(__file__).resolve().parents[1]
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{root / "run_home.pyw"}"'


def autostart_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                        winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


def _single_instance():
    """Keeps a named mutex for the life of the process; None if another copy holds it."""
    if os.name != "nt":
        return True
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def _message(text: str) -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Voice Typer Home", 0x40)
    else:
        print(text)


def _copy(text: str) -> None:
    import tkinter as tk

    r = tk.Tk()
    r.withdraw()
    r.clipboard_clear()
    r.clipboard_append(text)
    r.update()
    r.after(500, r.destroy)
    r.mainloop()


def run(port: int = 8765) -> None:
    from voice_typer import __version__, portable
    from voice_typer.tray import _icon_image

    portable.use_private_temp()
    mutex = _single_instance()
    if mutex is None:
        _message("Voice Typer Home est déjà ouvert (icône bleue près de l'horloge).")
        return
    log = setup_log()
    key = load_or_create_key()
    models = Models(log=log.info)
    try:
        server = make_server(models, key, port, __version__)
    except OSError as exc:
        _message(f"Impossible d'utiliser le port {port} : {exc}\nUn autre programme l'utilise peut-être.")
        return
    log.info(f"Voice Typer Home {__version__} démarré (127.0.0.1:{port})")

    import pystray

    icon = None

    def menu():
        items = [pystray.MenuItem(line, None, enabled=False) for line in status_lines(models.status())]
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Copier la clé", lambda: threading.Thread(target=_copy, args=(key,)).start()),
            pystray.MenuItem("Ouvrir le journal", lambda: os.startfile(home_dir() / "home.log")),  # noqa: S606
            pystray.MenuItem("Démarrer avec Windows", lambda: (set_autostart(not autostart_enabled()), refresh()),
                             checked=lambda _i: autostart_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", lambda: (server.shutdown(), icon.stop())),
        ]
        return pystray.Menu(*items)

    def refresh():
        if icon:
            icon.menu = menu()
            try:
                icon.update_menu()
            except Exception:  # noqa: BLE001
                pass

    def on_event(kind, source, device, error):
        refresh()
        msg = load_message(kind, source, device, error)
        if msg and icon:
            log.info(msg)
            try:
                icon.notify(msg, "Voice Typer Home")
            except Exception:  # noqa: BLE001
                pass

    models.on_event = on_event
    models.configure()
    log.info(f"Modèles de ce PC : {models.defaults['whisper']}, {models.defaults['writer']}")
    icon = pystray.Icon("VoiceTyperHome", _icon_image(BLUE), "Voice Typer Home", menu())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    models.preload()
    def keep_menu_fresh():   # "chargement de …" lines change while models load
        while True:
            time.sleep(5)
            refresh()

    threading.Thread(target=keep_menu_fresh, daemon=True).start()
    icon.run()
    server.server_close()
    log.info("Voice Typer Home arrêté")
