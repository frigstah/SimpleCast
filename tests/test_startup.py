import unittest
from unittest.mock import Mock, patch

from simplecast.startup import (
    VALUE_NAME,
    set_start_with_windows,
    startup_command,
)


class StartupRegistrationTests(unittest.TestCase):
    @patch("simplecast.startup.subprocess.list2cmdline")
    def test_packaged_command_uses_executable_and_startup_flag(
        self,
        list2cmdline,
    ) -> None:
        list2cmdline.return_value = "command"
        with (
            patch("simplecast.startup.sys.frozen", True, create=True),
            patch("simplecast.startup.sys.executable", r"C:\SimpleCast\SimpleCast.exe"),
        ):
            self.assertEqual(startup_command(), "command")
        arguments = list2cmdline.call_args.args[0]
        self.assertEqual(arguments[-1], "--startup")
        self.assertTrue(arguments[0].endswith("SimpleCast.exe"))

    @patch("simplecast.startup.winreg.SetValueEx")
    @patch("simplecast.startup.winreg.CreateKeyEx")
    def test_enabling_writes_current_user_run_value(
        self,
        create_key,
        set_value,
    ) -> None:
        key = Mock()
        create_key.return_value.__enter__.return_value = key
        with patch("simplecast.startup.startup_command", return_value="SimpleCast --startup"):
            set_start_with_windows(True)
        self.assertEqual(set_value.call_args.args[1], VALUE_NAME)
        self.assertEqual(set_value.call_args.args[4], "SimpleCast --startup")


if __name__ == "__main__":
    unittest.main()
