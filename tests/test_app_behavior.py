from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from simplecast.app import SimpleCastApp


class BroadcastStopBehaviorTests(unittest.TestCase):
    @staticmethod
    def _app(confirm: bool) -> tuple[SimpleNamespace, Mock]:
        stream = Mock()
        stream.active = True
        app = SimpleNamespace(
            _auto_start_active=False,
            config=SimpleNamespace(confirm_stop_broadcast=confirm),
            stream=stream,
            broadcast_button=Mock(),
        )
        return app, stream

    def test_stop_does_not_prompt_when_confirmation_is_disabled(self) -> None:
        app, stream = self._app(False)
        with patch(
            "simplecast.app.messagebox.askyesno",
            side_effect=AssertionError("confirmation should not open"),
        ):
            SimpleCastApp.toggle_broadcast(app)
        stream.stop.assert_called_once_with()

    def test_stop_respects_a_cancelled_confirmation(self) -> None:
        app, stream = self._app(True)
        with patch(
            "simplecast.app.messagebox.askyesno",
            return_value=False,
        ):
            SimpleCastApp.toggle_broadcast(app)
        stream.stop.assert_not_called()

    def test_stop_continues_after_confirmation(self) -> None:
        app, stream = self._app(True)
        with patch(
            "simplecast.app.messagebox.askyesno",
            return_value=True,
        ):
            SimpleCastApp.toggle_broadcast(app)
        stream.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
