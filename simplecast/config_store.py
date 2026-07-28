from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import keyring

from .models import AppConfig


class ConfigStore:
    SERVICE = "SimpleCast"

    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(os.environ.get("APPDATA", Path.home())) / "SimpleCast"
        self.root = base
        self.path = base / "config.json"
        self.backup_path = base / "config.backup.json"

    def load(self) -> AppConfig:
        for candidate in (self.path, self.backup_path):
            if not candidate.exists():
                continue
            try:
                return AppConfig.from_dict(
                    json.loads(candidate.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError, TypeError):
                if candidate == self.path:
                    broken = self.path.with_suffix(".broken.json")
                    try:
                        self.path.replace(broken)
                    except OSError:
                        pass
        return AppConfig()

    def save(self, config: AppConfig) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        if self.path.exists():
            shutil.copy2(self.path, self.backup_path)
        temp.write_text(
            json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(self.path)

    def get_password(self, server_id: str) -> str:
        try:
            return keyring.get_password(self.SERVICE, server_id) or ""
        except keyring.errors.KeyringError:
            return ""

    def set_password(self, server_id: str, password: str) -> None:
        try:
            if password:
                keyring.set_password(self.SERVICE, server_id, password)
            else:
                keyring.delete_password(self.SERVICE, server_id)
        except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError):
            pass

    def delete_password(self, server_id: str) -> None:
        try:
            keyring.delete_password(self.SERVICE, server_id)
        except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError):
            pass
