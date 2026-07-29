import tempfile
import unittest
from pathlib import Path

from simplecast.config_store import ConfigStore
from simplecast.models import AppConfig, ServerProfile


class ServerProfileTests(unittest.TestCase):
    def test_normalizes_mount_and_defaults(self) -> None:
        server = ServerProfile(name=" ", mount="radio", username=" ").normalized()
        self.assertEqual(server.name, "My station")
        self.assertEqual(server.mount, "/radio")
        self.assertEqual(server.username, "source")

    def test_validation_rejects_bad_connection(self) -> None:
        server = ServerProfile(host="", port=70000, mount="/")
        self.assertEqual(len(server.validate()), 3)

    def test_shoutcast_does_not_require_mount_or_username(self) -> None:
        server = ServerProfile(
            server_type="shoutcast2",
            host="radio.example",
            mount="",
            username="",
            stream_id=2,
        ).normalized()
        self.assertEqual(server.mount, "")
        self.assertEqual(server.validate(), [])

    def test_old_profile_defaults_to_icecast(self) -> None:
        server = ServerProfile.from_dict(
            {"host": "radio.example", "mount": "live", "username": "source"}
        )
        self.assertEqual(server.server_type, "icecast2")
        self.assertEqual(server.mount, "/live")

    def test_sample_rate_is_loaded_and_invalid_values_are_repaired(self) -> None:
        self.assertEqual(
            AppConfig.from_dict({"output_sample_rate": 48000}).output_sample_rate,
            48000,
        )
        self.assertEqual(
            AppConfig.from_dict({"output_sample_rate": "invalid"}).output_sample_rate,
            44100,
        )

    def test_audio_system_is_saved_and_invalid_values_use_automatic(self) -> None:
        self.assertEqual(
            AppConfig.from_dict(
                {"audio_system": "Windows WASAPI (shared)"}
            ).audio_system,
            "Windows WASAPI (shared)",
        )
        self.assertEqual(
            AppConfig.from_dict({"audio_system": "Unknown"}).audio_system,
            "Automatic",
        )

    def test_invalid_startup_delay_uses_safe_default(self) -> None:
        self.assertEqual(
            AppConfig.from_dict({"startup_delay_seconds": 0}).startup_delay_seconds,
            10,
        )
        self.assertEqual(
            AppConfig.from_dict(
                {"startup_delay_seconds": "invalid"}
            ).startup_delay_seconds,
            10,
        )

    def test_ui_theme_is_saved_and_invalid_values_use_classic(self) -> None:
        self.assertEqual(
            AppConfig.from_dict({"ui_theme": "Modern & sleek"}).ui_theme,
            "Modern & sleek",
        )
        self.assertEqual(
            AppConfig.from_dict({"ui_theme": "Unknown"}).ui_theme,
            "Classic SimpleCast",
        )

    def test_ui_skin_is_saved_and_invalid_values_use_classic(self) -> None:
        self.assertEqual(
            AppConfig.from_dict({"ui_skin": "Studio Dark"}).ui_skin,
            "Studio Dark",
        )
        self.assertEqual(
            AppConfig.from_dict({"ui_skin": "Unknown"}).ui_skin,
            "Classic SimpleCast",
        )

    def test_old_quality_names_are_migrated(self) -> None:
        self.assertEqual(
            AppConfig.from_dict({"quality": "Standard"}).quality,
            "SL MAX unsafe",
        )
        self.assertEqual(
            AppConfig.from_dict({"quality": "High quality"}).quality,
            "Recording",
        )

    def test_processing_preset_is_validated(self) -> None:
        self.assertEqual(
            AppConfig.from_dict(
                {"processing_preset": "Mixed content"}
            ).processing_preset,
            "Mixed content",
        )
        self.assertEqual(
            AppConfig.from_dict(
                {"processing_preset": "Unknown"}
            ).processing_preset,
            "Off / Original",
        )

    def test_single_server_configuration_is_migrated_to_enabled_list(self) -> None:
        server = ServerProfile(host="radio.example")
        config = AppConfig.from_dict(
            {
                "selected_server_id": server.id,
                "servers": [server.to_dict()],
            }
        )
        self.assertEqual(config.enabled_server_ids, [server.id])

    def test_favorites_are_validated_and_deduplicated(self) -> None:
        servers = [
            ServerProfile(name=f"Station {index}", host=f"{index}.example")
            for index in range(8)
        ]
        first, second = servers[:2]
        config = AppConfig.from_dict(
            {
                "servers": [server.to_dict() for server in servers],
                "favorite_server_ids": [
                    second.id,
                    "missing",
                    second.id,
                    first.id,
                    *[server.id for server in servers[2:]],
                ],
            }
        )
        self.assertEqual(
            config.favorite_server_ids[:2],
            [second.id, first.id],
        )
        self.assertEqual(len(config.favorite_server_ids), 6)
        self.assertEqual(
            [server.id for server in config.favorite_servers()[:2]],
            [first.id, second.id],
        )

    def test_quick_switch_selects_one_valid_broadcast_destination(self) -> None:
        first = ServerProfile(name="First", host="one.example")
        second = ServerProfile(name="Second", host="two.example")
        config = AppConfig(
            selected_server_id=first.id,
            enabled_server_ids=[first.id, second.id],
            servers=[first, second],
        )
        self.assertTrue(config.select_only_server(second.id))
        self.assertEqual(config.selected_server_id, second.id)
        self.assertEqual(config.enabled_server_ids, [second.id])
        self.assertFalse(config.select_only_server("missing"))
        self.assertEqual(config.enabled_server_ids, [second.id])

    def test_personal_listener_peak_is_persisted_and_repaired(self) -> None:
        server = ServerProfile(
            host="radio.example",
            personal_listener_peak=42,
        )
        loaded = ServerProfile.from_dict(server.to_dict())
        self.assertEqual(loaded.personal_listener_peak, 42)
        repaired = ServerProfile.from_dict(
            {
                "host": "radio.example",
                "personal_listener_peak": -5,
            }
        )
        self.assertEqual(repaired.personal_listener_peak, 0)
        self.assertTrue(loaded.observe_listener_count(47))
        self.assertEqual(loaded.personal_listener_peak, 47)
        self.assertFalse(loaded.observe_listener_count(20))
        self.assertEqual(loaded.personal_listener_peak, 47)


class ConfigStoreTests(unittest.TestCase):
    def test_round_trip_does_not_contain_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            server = ServerProfile(host="radio.example", mount="/live")
            config = AppConfig(
                selected_server_id=server.id,
                enabled_server_ids=[server.id],
                favorite_server_ids=[server.id],
                input_volume_percent=135,
                processing_preset="Voice",
                recording_folder=r"D:\Radio Recordings",
                record_broadcasts=True,
                metadata_file=r"D:\Automation\now-playing.txt",
                metadata_auto=True,
                metadata_format="Artist - Title (first two lines)",
                start_with_windows=True,
                start_minimized=True,
                auto_broadcast=True,
                startup_delay_seconds=30,
                ui_theme="Beginner friendly",
                ui_skin="Studio Workspace",
                servers=[server],
            )
            store.save(config)
            raw = store.path.read_text(encoding="utf-8")
            loaded = store.load()
            self.assertNotIn("password", raw.lower())
            self.assertEqual(loaded.selected_server().host, "radio.example")
            self.assertEqual(loaded.input_volume_percent, 135)
            self.assertEqual(loaded.processing_preset, "Voice")
            self.assertEqual(loaded.recording_folder, r"D:\Radio Recordings")
            self.assertTrue(loaded.record_broadcasts)
            self.assertEqual(loaded.enabled_servers()[0].id, server.id)
            self.assertEqual(loaded.favorite_servers()[0].id, server.id)
            self.assertEqual(
                loaded.metadata_file,
                r"D:\Automation\now-playing.txt",
            )
            self.assertTrue(loaded.metadata_auto)
            self.assertEqual(
                loaded.metadata_format,
                "Artist - Title (first two lines)",
            )
            self.assertTrue(loaded.start_with_windows)
            self.assertTrue(loaded.start_minimized)
            self.assertTrue(loaded.auto_broadcast)
            self.assertEqual(loaded.startup_delay_seconds, 30)
            self.assertEqual(loaded.ui_theme, "Beginner friendly")
            self.assertEqual(loaded.ui_skin, "Studio Workspace")

    def test_broken_config_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            store.root.mkdir(exist_ok=True)
            store.path.write_text("{broken", encoding="utf-8")
            config = store.load()
            self.assertEqual(config.servers, [])
            self.assertTrue(store.path.with_suffix(".broken.json").exists())

    def test_backup_restores_last_good_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            first = AppConfig(input_volume_percent=125)
            store.save(first)
            store.save(AppConfig(input_volume_percent=150))
            store.path.write_text("{broken", encoding="utf-8")
            loaded = store.load()
            self.assertEqual(loaded.input_volume_percent, 125)


if __name__ == "__main__":
    unittest.main()
