from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from simplecast.app import (
    COLORS,
    WS_CAPTION,
    WS_MAXIMIZEBOX,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    WS_THICKFRAME,
    SimpleCastApp,
)
from simplecast.models import AppConfig, ServerProfile


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

    def test_minimize_stays_on_taskbar_by_default(self) -> None:
        app = SimpleNamespace(
            config=SimpleNamespace(minimize_to_tray=False),
            wm_state=Mock(return_value="iconic"),
            after=Mock(),
        )

        SimpleCastApp._on_unmap(app, object())

        app.after.assert_not_called()

    def test_opt_in_minimize_schedules_tray_hide(self) -> None:
        app = SimpleNamespace(
            config=SimpleNamespace(minimize_to_tray=True),
            wm_state=Mock(return_value="iconic"),
            after=Mock(),
            _minimize_to_tray=Mock(),
        )

        SimpleCastApp._on_unmap(app, object())

        app.after.assert_called_once_with(100, app._minimize_to_tray)


class RecordingFolderBehaviorTests(unittest.TestCase):
    def test_open_folder_creates_and_opens_configured_location(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "Recordings"
            app = SimpleNamespace(
                _recording_folder=Mock(return_value=destination),
            )
            with patch("simplecast.app.os.startfile") as startfile:
                SimpleCastApp.open_recording_folder(app)

            self.assertTrue(destination.is_dir())
            startfile.assert_called_once_with(str(destination))


class MiniModeBehaviorTests(unittest.TestCase):
    def test_server_order_places_favorites_first_in_saved_order(self) -> None:
        one = ServerProfile(name="One")
        two = ServerProfile(name="Two")
        three = ServerProfile(name="Three")
        config = AppConfig(
            servers=[one, two, three],
            favorite_server_ids=[three.id, one.id],
        )

        ordered = SimpleCastApp._mini_server_order(config)

        self.assertEqual(
            [server.id for server in ordered],
            [three.id, one.id, two.id],
        )

    def test_long_server_names_are_shortened_for_mini_mode(self) -> None:
        self.assertEqual(
            SimpleCastApp._mini_server_name("A very long station name", 12),
            "A very long…",
        )

    def test_server_menu_is_positioned_below_the_mini_selector(self) -> None:
        app = SimpleNamespace(
            update_idletasks=Mock(),
            winfo_screenwidth=Mock(return_value=1920),
            mini_server_button=SimpleNamespace(
                winfo_rootx=Mock(return_value=900),
                winfo_width=Mock(return_value=130),
                winfo_rooty=Mock(return_value=500),
                winfo_height=Mock(return_value=34),
            ),
            mini_dropdown=Mock(),
        )

        SimpleCastApp._position_mini_server_menu(app, 160)

        app.mini_dropdown.geometry.assert_called_once_with(
            "230x160+800+534"
        )

    @staticmethod
    def _listener_app(
        online_ids: set[str],
        counts: dict[str, int],
        errors: dict[str, str],
    ) -> SimpleNamespace:
        return SimpleNamespace(
            stream=SimpleNamespace(online_server_ids=online_ids),
            listener_counts=counts,
            listener_errors=errors,
        )

    def test_mini_listener_count_totals_online_servers(self) -> None:
        app = self._listener_app(
            {"one", "two"},
            {"one": 4, "two": 7},
            {},
        )

        text, color = SimpleCastApp._mini_listener_status(app)

        self.assertEqual(text, "LISTENERS: 11")
        self.assertEqual(color, COLORS["accent"])

    def test_mini_listener_count_marks_partial_totals(self) -> None:
        app = self._listener_app(
            {"one", "two"},
            {"one": 4},
            {"two": "Unavailable"},
        )

        text, color = SimpleCastApp._mini_listener_status(app)

        self.assertEqual(text, "LISTENERS: 4+")
        self.assertEqual(color, COLORS["accent"])

    def test_mini_listener_count_reports_unavailable(self) -> None:
        app = self._listener_app(
            {"one"},
            {},
            {"one": "Unavailable"},
        )

        text, color = SimpleCastApp._mini_listener_status(app)

        self.assertEqual(text, "LISTENERS: UNAVAILABLE")
        self.assertEqual(color, COLORS["muted"])


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
