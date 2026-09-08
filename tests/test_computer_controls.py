from app.computer.keyboard import Keyboard
from app.computer.mouse import Mouse


class FakeMouse:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def click(self, x: int, y: int, *, clicks: int = 1, button: str = "left") -> None:
        self.calls.append((x, y, clicks, button))


class FakeKeyboard:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def write(self, text: str, *, interval: float = 0.0) -> None:
        self.calls.append(("write", text, interval))

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", *keys))


def test_mouse_and_keyboard_delegate_to_injected_backends() -> None:
    mouse_backend, keyboard_backend = FakeMouse(), FakeKeyboard()
    Mouse(mouse_backend).click(10, 20)
    keyboard = Keyboard(keyboard_backend)
    keyboard.type_text("hello")
    keyboard.press_hotkey("ctrl", "c")
    assert mouse_backend.calls == [(10, 20, 1, "left")]
    assert keyboard_backend.calls == [("write", "hello", 0.01), ("hotkey", "ctrl", "c")]
