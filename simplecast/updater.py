from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RELEASES_URL = (
    "https://api.github.com/repos/frigstah/SimpleCast/releases?per_page=20"
)
REPOSITORY_RELEASE_PATH = "/frigstah/SimpleCast/releases/"
MAX_RELEASE_RESPONSE_BYTES = 5 * 1024 * 1024
VERSION_PATTERN = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)"
    r"(?:-(alpha|beta|rc)[.-]?(\d+))?$",
    re.IGNORECASE,
)


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, verified, or prepared."""


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class UpdateRelease:
    version: str
    tag: str
    name: str
    notes: str
    page_url: str
    prerelease: bool
    installer: ReleaseAsset


def version_key(version: str) -> tuple[int, int, int, int, int] | None:
    match = VERSION_PATTERN.fullmatch(version.strip())
    if match is None:
        return None
    major, minor, patch = (int(match.group(index)) for index in range(1, 4))
    label = (match.group(4) or "").lower()
    number = int(match.group(5) or 0)
    release_rank = {
        "alpha": 0,
        "beta": 1,
        "rc": 2,
        "": 3,
    }[label]
    return major, minor, patch, release_rank, number


def _trusted_release_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.path.startswith(REPOSITORY_RELEASE_PATH)
    )


def _release_from_document(document: dict[str, Any]) -> UpdateRelease | None:
    if document.get("draft"):
        return None
    tag = str(document.get("tag_name", "")).strip()
    key = version_key(tag)
    if key is None:
        return None
    version = tag[1:] if tag[:1].lower() == "v" else tag
    expected_name = f"SimpleCast-Setup-{version}-x64.exe"
    assets = document.get("assets", [])
    if not isinstance(assets, list):
        return None
    installer_document = next(
        (
            asset
            for asset in assets
            if isinstance(asset, dict)
            and asset.get("state") == "uploaded"
            and asset.get("name") == expected_name
        ),
        None,
    )
    if installer_document is None:
        return None
    digest = str(installer_document.get("digest", ""))
    if not digest.lower().startswith("sha256:"):
        return None
    sha256 = digest.split(":", 1)[1].strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        return None
    download_url = str(installer_document.get("browser_download_url", ""))
    page_url = str(document.get("html_url", ""))
    if not _trusted_release_url(download_url) or not _trusted_release_url(page_url):
        return None
    try:
        size = int(installer_document.get("size", 0))
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    return UpdateRelease(
        version=version,
        tag=tag,
        name=str(document.get("name") or tag),
        notes=str(document.get("body") or ""),
        page_url=page_url,
        prerelease=bool(document.get("prerelease")),
        installer=ReleaseAsset(
            name=expected_name,
            download_url=download_url,
            size=size,
            sha256=sha256,
        ),
    )


def select_update(
    current_version: str,
    documents: list[dict[str, Any]],
    include_prereleases: bool = True,
) -> UpdateRelease | None:
    current_key = version_key(current_version)
    if current_key is None:
        raise UpdateError(f"SimpleCast has an unknown version: {current_version}")
    candidates = []
    for document in documents:
        release = _release_from_document(document)
        if release is None:
            continue
        if release.prerelease and not include_prereleases:
            continue
        key = version_key(release.version)
        if key is not None and key > current_key:
            candidates.append((key, release))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def check_for_update(
    current_version: str,
    include_prereleases: bool = True,
    timeout: float = 10,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> UpdateRelease | None:
    request = urllib.request.Request(
        RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"SimpleCast/{current_version} updater",
        },
    )
    with opener(request, timeout=timeout) as response:
        payload = response.read(MAX_RELEASE_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RELEASE_RESPONSE_BYTES:
        raise UpdateError("GitHub returned an unexpectedly large release list")
    try:
        documents = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError("GitHub returned an invalid release list") from error
    if not isinstance(documents, list):
        raise UpdateError("GitHub returned an unknown release format")
    return select_update(
        current_version,
        [item for item in documents if isinstance(item, dict)],
        include_prereleases,
    )


def download_installer(
    release: UpdateRelease,
    progress_callback: Callable[[int, int], None] | None = None,
    timeout: float = 30,
    opener: Callable[..., Any] = urllib.request.urlopen,
    destination_root: Path | None = None,
) -> Path:
    root = destination_root or Path(tempfile.gettempdir()) / "SimpleCast-update"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / release.installer.name
    partial = destination.with_suffix(f"{destination.suffix}.part")
    request = urllib.request.Request(
        release.installer.download_url,
        headers={"User-Agent": f"SimpleCast/{release.version} updater"},
    )
    digest = hashlib.sha256()
    received = 0
    try:
        with opener(request, timeout=timeout) as response:
            with partial.open("wb") as output:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    output.write(block)
                    digest.update(block)
                    received += len(block)
                    if progress_callback is not None:
                        progress_callback(received, release.installer.size)
        if received != release.installer.size:
            raise UpdateError(
                "The downloaded installer size does not match the GitHub release"
            )
        if digest.hexdigest().lower() != release.installer.sha256:
            raise UpdateError(
                "The downloaded installer failed SHA-256 verification"
            )
        partial.replace(destination)
        return destination
    except Exception:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        raise
