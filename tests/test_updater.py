import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from simplecast.updater import (
    UpdateError,
    check_for_update,
    download_installer,
    select_update,
    version_key,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.stream = io.BytesIO(payload)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


def release_document(
    version: str,
    payload: bytes = b"installer",
    *,
    draft: bool = False,
    prerelease: bool = True,
    digest: str | None = None,
) -> dict:
    tag = f"v{version}"
    filename = f"SimpleCast-Setup-{version}-x64.exe"
    return {
        "tag_name": tag,
        "name": f"SimpleCast {version}",
        "body": "Release notes",
        "html_url": (
            f"https://github.com/frigstah/SimpleCast/releases/tag/{tag}"
        ),
        "draft": draft,
        "prerelease": prerelease,
        "assets": [
            {
                "name": filename,
                "state": "uploaded",
                "size": len(payload),
                "digest": (
                    digest
                    if digest is not None
                    else f"sha256:{hashlib.sha256(payload).hexdigest()}"
                ),
                "browser_download_url": (
                    "https://github.com/frigstah/SimpleCast/releases/"
                    f"download/{tag}/{filename}"
                ),
            }
        ],
    }


class VersionTests(unittest.TestCase):
    def test_orders_beta_rc_and_stable_versions(self) -> None:
        self.assertLess(
            version_key("0.9.0-beta.4"),
            version_key("0.9.0-rc.1"),
        )
        self.assertLess(
            version_key("0.9.0-rc.1"),
            version_key("0.9.0"),
        )
        self.assertLess(
            version_key("0.9.0"),
            version_key("0.10.0-beta.1"),
        )

    def test_selects_newest_published_beta(self) -> None:
        selected = select_update(
            "0.9.0-beta.4",
            [
                release_document("0.9.0-beta.5"),
                release_document("0.9.0-beta.6", draft=True),
                release_document("0.9.0-beta.3"),
            ],
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.version, "0.9.0-beta.5")

    def test_can_exclude_prereleases(self) -> None:
        selected = select_update(
            "0.9.0-beta.4",
            [release_document("0.9.0-beta.5")],
            include_prereleases=False,
        )
        self.assertIsNone(selected)

    def test_rejects_an_asset_without_a_github_digest(self) -> None:
        selected = select_update(
            "0.9.0-beta.4",
            [release_document("0.9.0-beta.5", digest="")],
        )
        self.assertIsNone(selected)


class UpdateNetworkTests(unittest.TestCase):
    def test_checks_the_public_release_list(self) -> None:
        payload = json.dumps(
            [release_document("0.9.0-beta.5")]
        ).encode("utf-8")
        seen_urls: list[str] = []

        def opener(request: object, timeout: float) -> FakeResponse:
            self.assertEqual(timeout, 10)
            seen_urls.append(request.full_url)
            return FakeResponse(payload)

        release = check_for_update(
            "0.9.0-beta.4",
            opener=opener,
        )
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "0.9.0-beta.5")
        self.assertIn("api.github.com/repos/frigstah/SimpleCast", seen_urls[0])

    def test_downloads_and_verifies_the_installer(self) -> None:
        payload = b"verified installer bytes"
        release = select_update(
            "0.9.0-beta.4",
            [release_document("0.9.0-beta.5", payload)],
        )
        self.assertIsNotNone(release)
        progress: list[tuple[int, int]] = []

        def opener(_request: object, timeout: float) -> FakeResponse:
            self.assertEqual(timeout, 30)
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as directory:
            path = download_installer(
                release,
                opener=opener,
                destination_root=Path(directory),
                progress_callback=lambda received, total: (
                    progress.append((received, total))
                ),
            )
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(progress[-1], (len(payload), len(payload)))

    def test_removes_a_download_with_the_wrong_hash(self) -> None:
        expected = b"expected"
        downloaded = b"tampered"
        release = select_update(
            "0.9.0-beta.4",
            [release_document("0.9.0-beta.5", expected)],
        )
        self.assertIsNotNone(release)

        def opener(_request: object, timeout: float) -> FakeResponse:
            del timeout
            return FakeResponse(downloaded)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UpdateError):
                download_installer(
                    release,
                    opener=opener,
                    destination_root=Path(directory),
                )
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
