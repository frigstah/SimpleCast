from __future__ import annotations

from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw


def _create_icon() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (13, 23, 38, 255))
    draw = ImageDraw.Draw(image)
    accent = (76, 212, 167, 255)
    draw.ellipse((26, 26, 38, 38), fill=accent)
    draw.arc((16, 16, 48, 48), 300, 60, fill=accent, width=4)
    draw.arc((7, 7, 57, 57), 300, 60, fill=accent, width=4)
    draw.arc((16, 16, 48, 48), 120, 240, fill=accent, width=4)
    draw.arc((7, 7, 57, 57), 120, 240, fill=accent, width=4)
    return image


class TrayController:
    def __init__(
        self,
        show_window: Callable[[], None],
        toggle_broadcast: Callable[[], None],
        exit_app: Callable[[], None],
        is_broadcasting: Callable[[], bool],
    ) -> None:
        self.show_window = show_window
        self.toggle_broadcast = toggle_broadcast
        self.exit_app = exit_app
        self.is_broadcasting = is_broadcasting
        self.icon = pystray.Icon(
            "SimpleCast",
            _create_icon(),
            "SimpleCast",
            menu=pystray.Menu(
                pystray.MenuItem("Open SimpleCast", self._show, default=True),
                pystray.MenuItem(self._broadcast_label, self._toggle),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self._exit),
            ),
        )

    def start(self) -> None:
        self.icon.run_detached()

    def stop(self) -> None:
        self.icon.stop()

    def update(self, status: str) -> None:
        self.icon.title = f"SimpleCast — {status}"
        self.icon.update_menu()

    def notify(self, title: str, message: str) -> None:
        try:
            self.icon.notify(message, title)
        except (NotImplementedError, OSError):
            pass

    def _broadcast_label(self, _item: pystray.MenuItem) -> str:
        return "Stop broadcast" if self.is_broadcasting() else "Start broadcast"

    def _show(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.show_window()

    def _toggle(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.toggle_broadcast()

    def _exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.exit_app()
