"""Global hotkey that *swallows* its trigger key so it never reaches the focused app.

The last key of the combo is the trigger (e.g. "space" in "ctrl+alt+space"). Its key events
(including auto-repeat while held) are suppressed whenever the modifiers are held, so the
app underneath never receives stray spaces or shortcuts. When Alt or Win is part of the combo,
a harmless "mask" key is injected so releasing Alt/Win doesn't open a menu or the Start menu.
"""

import ctypes
import queue
import threading
import traceback
from collections.abc import Callable

import keyboard

MODIFIERS = {
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "alt", "left alt", "right alt", "alt gr",
    "windows", "left windows", "right windows",
}
_MENU_MODIFIERS = {"alt", "left alt", "right alt", "alt gr", "windows", "left windows", "right windows"}
SINGLE_KEYS_OK = {f"f{i}" for i in range(1, 25)} | {
    "right ctrl", "right shift", "right alt", "pause", "scroll lock", "insert", "menu", "caps lock",
}
_MASK_VK = 0xE8  # unassigned virtual key


def _send_mask_key() -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(_MASK_VK, 0, 0, 0)
    user32.keybd_event(_MASK_VK, 0, 2, 0)


def normalize(combo: str) -> list[str]:
    return [p.strip().lower() for p in combo.split("+") if p.strip()]


def validate(combo: str) -> str | None:
    """Return an error code if the combo can't be used, else None."""
    parts = normalize(combo)
    if not parts:
        return "empty"
    try:
        for p in parts:
            keyboard.key_to_scan_codes(p)
    except ValueError:
        return "unknown"
    has_modifier = any(p in MODIFIERS for p in parts[:-1])
    if len(parts) == 1 and parts[0] not in SINGLE_KEYS_OK:
        return "single"  # a lone letter/space would block normal typing
    if len(parts) > 1 and not has_modifier:
        return "single"
    if set(parts[:-1]) <= {"shift", "left shift", "right shift"} and len(parts[-1]) == 1:
        return "single"  # Shift+letter is just a capital letter
    return None


class Hotkey:
    def __init__(self, combo: str, on_down: Callable[[], None], on_up: Callable[[], None]):
        self.on_down = on_down
        self.on_up = on_up
        self._hook = None
        self._active = False
        self._calls: queue.Queue[Callable[[], None]] = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()
        self.set_combo(combo)

    def set_combo(self, combo: str) -> None:
        parts = normalize(combo)
        self.combo = "+".join(parts)
        self.trigger = parts[-1]
        self.mods = parts[:-1]
        self.trigger_codes = set(keyboard.key_to_scan_codes(self.trigger))
        self._needs_mask = any(m in _MENU_MODIFIERS for m in self.mods) or self.trigger in _MENU_MODIFIERS
        self._active = False

    # The low-level hook must return quickly, so callbacks run on a worker thread (in order).
    def _worker(self) -> None:
        while True:
            fn = self._calls.get()
            try:
                fn()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    def _handler(self, event: keyboard.KeyboardEvent) -> bool:
        if event.scan_code not in self.trigger_codes:
            return True
        if event.event_type == keyboard.KEY_DOWN:
            if self._active:
                return False  # auto-repeat while held: swallow
            if all(keyboard.is_pressed(m) for m in self.mods):
                self._active = True
                if self._needs_mask:
                    _send_mask_key()
                self._calls.put(self.on_down)
                return False
            return True
        if self._active:  # key up
            self._active = False
            if self._needs_mask:
                _send_mask_key()
            self._calls.put(self.on_up)
            return False
        return True

    def modifiers_held(self) -> bool:
        return any(keyboard.is_pressed(m) for m in self.mods)

    def start(self) -> None:
        if self._hook is None:
            self._hook = keyboard.hook(self._handler, suppress=True)

    def stop(self) -> None:
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        self._active = False
