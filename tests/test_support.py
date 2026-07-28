import unittest

from simplecast.support import sanitize_support_text


class SupportReportTests(unittest.TestCase):
    def test_redacts_url_and_named_credentials(self) -> None:
        source = (
            "icecast://source:super-secret@radio.example/live "
            "password=another-secret secret: third-secret"
        )
        sanitized = sanitize_support_text(source)
        self.assertNotIn("super-secret", sanitized)
        self.assertNotIn("another-secret", sanitized)
        self.assertNotIn("third-secret", sanitized)
        self.assertIn("icecast://source:***@radio.example/live", sanitized)


if __name__ == "__main__":
    unittest.main()
