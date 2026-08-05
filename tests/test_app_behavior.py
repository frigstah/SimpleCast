from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from simplecast.app import (
    COLORS,
    DWMWA_BORDER_COLOR,
    DWMWA_CAPTION_COLOR,
    DWMWA_TEXT_COLOR,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    SUPPORT_EASTER_EGG,
    StationManagerPage,
    SimpleCastApp,
)
from simplecast.butt_import import ButtServer, ButtServerExport
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
    def test_colorref_converts_rgb_to_win32_bgr_order(self) -> None:
        self.assertEqual(
            SimpleCastApp._colorref("#112233"),
            0x00332211,
        )

    def test_titlebar_mode_follows_color_luminance(self) -> None:
        self.assertTrue(SimpleCastApp._is_dark_color("#081017"))
        self.assertFalse(SimpleCastApp._is_dark_color("#eff8f7"))

    def test_native_frame_styling_only_calls_dwm(self) -> None:
        get_parent = Mock(return_value=4321)
        set_attribute = Mock(return_value=0)
        windll = SimpleNamespace(
            user32=SimpleNamespace(GetParent=get_parent),
            dwmapi=SimpleNamespace(
                DwmSetWindowAttribute=set_attribute,
            ),
        )
        app = SimpleNamespace(
            update_idletasks=Mock(),
            winfo_id=Mock(return_value=1234),
        )

        with (
            patch("simplecast.app.platform.system", return_value="Windows"),
            patch("simplecast.app.ctypes.windll", windll),
        ):
            applied = SimpleCastApp._style_native_window_frame(app)

        self.assertTrue(applied)
        self.assertEqual(
            [call.args[1] for call in set_attribute.call_args_list],
            [
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                DWMWA_CAPTION_COLOR,
                DWMWA_TEXT_COLOR,
                DWMWA_BORDER_COLOR,
            ],
        )
        self.assertFalse(
            hasattr(windll.user32, "SetWindowLongPtrW")
        )

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

    def test_startup_height_grows_to_fit_dashboard(self) -> None:
        app = SimpleNamespace(
            content_canvas=SimpleNamespace(
                winfo_height=Mock(return_value=700)
            ),
            page_host=SimpleNamespace(
                winfo_reqheight=Mock(return_value=825)
            ),
        )

        height = SimpleCastApp._startup_height_for_dashboard(app, 900)

        self.assertEqual(height, 1025)

    def test_missing_brand_assets_use_generated_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "missing"
            with (
                patch(
                    "simplecast.app._resource_path",
                    side_effect=lambda *_parts: missing,
                ),
                self.assertLogs(level="WARNING") as captured,
            ):
                image = SimpleCastApp._load_brand_image(24)

        self.assertEqual(image.size, (24, 24))
        self.assertEqual(image.mode, "RGBA")
        self.assertIsNotNone(image.getbbox())
        self.assertTrue(
            any(
                "using a generated fallback" in message
                for message in captured.output
            )
        )


class SupportPageTests(unittest.TestCase):
    def test_quality_control_credit_is_kept_verbatim(self) -> None:
        self.assertEqual(
            SUPPORT_EASTER_EGG,
            "“Elite QC, supporter and onboarder: Urban Harvy”",
        )


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


class ButtImportBehaviorTests(unittest.TestCase):
    def test_first_import_selects_only_butts_previous_station(self) -> None:
        first = ButtServer(
            ServerProfile(
                name="First",
                server_type="shoutcast1",
                host="one.example",
            ).normalized(),
            "first-secret",
        )
        previous = ButtServer(
            ServerProfile(
                name="Previously selected",
                server_type="icecast2",
                host="two.example",
                mount="/live",
            ).normalized(),
            "second-secret",
        )
        export = ButtServerExport(
            servers=(first, previous),
            selected_server_name="Previously selected",
        )
        store = Mock()
        app = SimpleNamespace(
            stream=SimpleNamespace(active=False),
            config=AppConfig(),
            store=store,
            save_config=Mock(),
            refresh_station=Mock(),
        )
        page = SimpleNamespace(app=app, refresh=Mock())

        with (
            patch(
                "simplecast.app.filedialog.askopenfilename",
                return_value="BUTT export",
            ),
            patch(
                "simplecast.app.load_butt_server_export",
                return_value=export,
            ),
            patch("simplecast.app.messagebox.askyesno", return_value=True),
            patch("simplecast.app.messagebox.showinfo"),
        ):
            StationManagerPage.import_butt_export(page)

        self.assertEqual(len(app.config.servers), 2)
        self.assertEqual(app.config.selected_server_id, previous.profile.id)
        self.assertEqual(
            app.config.enabled_server_ids,
            [previous.profile.id],
        )
        self.assertEqual(store.set_password.call_count, 2)
        app.save_config.assert_called_once_with()
        page.refresh.assert_called_once_with()
        app.refresh_station.assert_called_once_with()

    def test_import_keeps_an_existing_broadcast_selection(self) -> None:
        current = ServerProfile(
            name="Current",
            host="current.example",
        ).normalized()
        imported = ButtServer(
            ServerProfile(
                name="Imported",
                server_type="shoutcast1",
                host="new.example",
            ).normalized(),
            "new-secret",
        )
        config = AppConfig(
            selected_server_id=current.id,
            enabled_server_ids=[current.id],
            servers=[current],
        )
        store = Mock()
        store.get_password.return_value = "current-secret"
        app = SimpleNamespace(
            stream=SimpleNamespace(active=False),
            config=config,
            store=store,
            save_config=Mock(),
            refresh_station=Mock(),
        )
        page = SimpleNamespace(app=app, refresh=Mock())

        with (
            patch(
                "simplecast.app.filedialog.askopenfilename",
                return_value="BUTT export",
            ),
            patch(
                "simplecast.app.load_butt_server_export",
                return_value=ButtServerExport(servers=(imported,)),
            ),
            patch("simplecast.app.messagebox.askyesno", return_value=True),
            patch("simplecast.app.messagebox.showinfo"),
        ):
            StationManagerPage.import_butt_export(page)

        self.assertEqual(app.config.selected_server_id, current.id)
        self.assertEqual(app.config.enabled_server_ids, [current.id])
        self.assertEqual(len(app.config.servers), 2)


class StationFavoriteBehaviorTests(unittest.TestCase):
    def test_clicking_favorite_cell_toggles_that_station_directly(self) -> None:
        station = ServerProfile(name="Direct favorite")
        tree = Mock()
        tree.identify_region.return_value = "cell"
        tree.identify_column.return_value = "#2"
        tree.identify_row.return_value = station.id
        toggle = Mock()
        page = SimpleNamespace(
            app=SimpleNamespace(
                config=AppConfig(servers=[station]),
            ),
            tree=tree,
            _toggle_favorite_profile=toggle,
        )

        result = StationManagerPage._tree_clicked(
            page,
            SimpleNamespace(x=100, y=40),
        )

        self.assertEqual(result, "break")
        tree.selection_set.assert_called_once_with(station.id)
        tree.focus.assert_called_once_with(station.id)
        toggle.assert_called_once_with(station)

    def test_favorite_profile_can_be_added_and_removed(self) -> None:
        station = ServerProfile(name="Favorite")
        app = SimpleNamespace(
            config=AppConfig(servers=[station]),
            save_config=Mock(),
            refresh_station=Mock(),
        )
        page = SimpleNamespace(app=app, refresh=Mock())

        StationManagerPage._toggle_favorite_profile(page, station)
        self.assertEqual(
            app.config.favorite_server_ids,
            [station.id],
        )

        StationManagerPage._toggle_favorite_profile(page, station)
        self.assertEqual(app.config.favorite_server_ids, [])
        self.assertEqual(app.save_config.call_count, 2)
        self.assertEqual(page.refresh.call_count, 2)
        self.assertEqual(app.refresh_station.call_count, 2)

    def test_double_clicking_favorite_cell_does_not_open_editor(self) -> None:
        tree = Mock()
        tree.identify_region.return_value = "cell"
        tree.identify_column.return_value = "#2"
        page = SimpleNamespace(tree=tree, edit=Mock())

        result = StationManagerPage._tree_double_clicked(
            page,
            SimpleNamespace(x=100, y=40),
        )

        self.assertEqual(result, "break")
        page.edit.assert_not_called()

    def test_station_mousewheel_scrolls_only_the_station_list(self) -> None:
        page = SimpleNamespace(tree=Mock())

        result = StationManagerPage._scroll_tree(
            page,
            SimpleNamespace(delta=120),
        )

        self.assertEqual(result, "break")
        page.tree.yview_scroll.assert_called_once_with(-1, "units")

    def test_station_page_disables_outer_page_wheel_scrolling(self) -> None:
        app = SimpleNamespace(_active_page_name="Stations")

        result = SimpleCastApp._scroll_content(
            app,
            SimpleNamespace(x_root=100, y_root=100, delta=-120),
        )

        self.assertIsNone(result)


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


class ProgramSourceListBehaviorTests(unittest.TestCase):
    def test_advanced_process_list_setting_saves_and_refreshes(self) -> None:
        app = SimpleNamespace(
            config=SimpleNamespace(show_all_program_audio_sources=False),
            show_all_program_audio_sources_var=Mock(
                get=Mock(return_value=True)
            ),
            save_config=Mock(),
            refresh_devices=Mock(),
        )

        SimpleCastApp._program_audio_list_setting_changed(app)

        self.assertTrue(app.config.show_all_program_audio_sources)
        app.save_config.assert_called_once_with()
        app.refresh_devices.assert_called_once_with()


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
