from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from simplecast.app import (
    WS_CAPTION,
    WS_MAXIMIZEBOX,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    WS_THICKFRAME,
    SimpleCastApp,
)


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


class WindowChromeTests(unittest.TestCase):
    def test_integrated_style_removes_native_frame_drawing(self) -> None:
        original = (
            WS_CAPTION
            | WS_THICKFRAME
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
            | WS_SYSMENU
        )
        styled = SimpleCastApp._integrated_window_style(original)

        self.assertFalse(styled & WS_CAPTION)
        self.assertFalse(styled & WS_THICKFRAME)
        self.assertTrue(styled & WS_MINIMIZEBOX)
        self.assertTrue(styled & WS_MAXIMIZEBOX)
        self.assertTrue(styled & WS_SYSMENU)


class ProgramVolumeBehaviorTests(unittest.TestCase):
    @staticmethod
    def _app(enabled: bool) -> SimpleNamespace:
        return SimpleNamespace(
            config=SimpleNamespace(
                program_audio_enabled=enabled,
                program_volume_percent=135,
            ),
            program_volume_slider=Mock(),
            program_volume_reset_button=Mock(),
            program_volume_title=Mock(),
            program_volume_label=Mock(),
        )

    def test_program_volume_clearly_shows_when_it_is_off(self) -> None:
        app = self._app(False)
        SimpleCastApp._update_program_volume_controls(app)
        app.program_volume_slider.configure.assert_called_once_with(
            state="disabled"
        )
        app.program_volume_title.configure.assert_called_once_with(
            text="Program audio volume — off"
        )
        app.program_volume_label.configure.assert_called_once_with(
            text="Off",
            style="CardMuted.TLabel",
        )

    def test_program_volume_restores_saved_value_when_enabled(self) -> None:
        app = self._app(True)
        SimpleCastApp._update_program_volume_controls(app)
        app.program_volume_slider.configure.assert_called_once_with(
            state="normal"
        )
        app.program_volume_label.configure.assert_called_once_with(
            text="135%",
            style="Card.TLabel",
        )


class SoundTestBehaviorTests(unittest.TestCase):
    def test_successful_sound_test_restarts_meter_once(self) -> None:
        selection = object()
        audio = Mock()
        audio.record_test.return_value = (0.2, 0.4)
        app = SimpleNamespace(
            _capture_selection=Mock(return_value=selection),
            _capture_meter_level=Mock(),
            _start_meter=Mock(),
            audio=audio,
            config=SimpleNamespace(audio_system="Automatic"),
            current_device=object(),
            last_test_path=object(),
            processed_test_path=object(),
            processing_var=Mock(get=Mock(return_value="Off / Original")),
            sound_button=Mock(),
            play_original_button=Mock(),
            play_processed_button=Mock(),
            sound_hint=Mock(),
            after=lambda _delay, callback: callback(),
            _test_ready=False,
        )

        class ImmediateThread:
            def __init__(self, *, target, daemon) -> None:
                self.target = target

            def start(self) -> None:
                self.target()

        with (
            patch("simplecast.app.threading.Thread", ImmediateThread),
            patch("simplecast.app.process_test_file"),
            patch("simplecast.app.AudioEngine.play_file"),
        ):
            SimpleCastApp.test_sound(app)

        self.assertTrue(app._test_ready)
        app._start_meter.assert_called_once_with()
        self.assertIs(
            audio.record_test.call_args.kwargs["level_callback"],
            app._capture_meter_level,
        )


if __name__ == "__main__":
    unittest.main()
