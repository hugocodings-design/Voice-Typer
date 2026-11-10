"""Global push-to-talk hotkey: on_press when the combo goes down, on_release when it comes up."""

from collections.abc import Callable

import keyboard


class PushToTalk:
    def __init__(self, combo: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.combo = combo
        self.on_press = on_press
        self.on_release = on_release
        self._held = False
        self._keys = [k.strip() for k in combo.split("+")]

    def _handler(self, event: keyboard.KeyboardEvent) -> None:
        all_down = all(keyboard.is_pressed(k) for k in self._keys)
        if all_down and not self._held:
            self._held = True
            self.on_press()
        elif self._held and not all_down:
            self._held = False
            self.on_release()

    def start(self) -> None:
        keyboard.hook(self._handler)

    def stop(self) -> None:
        keyboard.unhook_all()
