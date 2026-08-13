from __future__ import annotations

import json
from pathlib import Path

from .alias_cleanup import synchronize_alias_files
from .catalog import ALIASES_PATH, CATALOG_PATH, normalize_phrase
from .config import USER_CONFIG_ROOT
from .storage import atomic_write_text


ENGLISH_ALIASES_PATH = USER_CONFIG_ROOT / "english_aliases.json"
ALIAS_ARCHIVE_PATH = USER_CONFIG_ROOT / "alias_archive.json"


class AliasStore:
    def __init__(
        self,
        catalog_path: Path = CATALOG_PATH,
        georgian_path: Path = ALIASES_PATH,
        english_path: Path = ENGLISH_ALIASES_PATH,
        archive_path: Path | None = None,
    ) -> None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.app_names = sorted({entry["name"] for entry in catalog}, key=str.casefold)
        self.paths = {"ka": georgian_path, "en": english_path}
        synchronize_alias_files(
            set(self.app_names),
            georgian_path,
            english_path,
            archive_path or georgian_path.with_name("alias_archive.json"),
        )
        self.data = {
            language: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            for language, path in self.paths.items()
        }

    def aliases(self, app_name: str, language: str) -> list[str]:
        return list(self.data[language].get(app_name, []))

    def owner(self, alias: str, language: str) -> str | None:
        normalized = normalize_phrase(alias)
        for app_name, aliases in self.data[language].items():
            if any(normalize_phrase(existing) == normalized for existing in aliases):
                return app_name
        return None

    def add(self, app_name: str, language: str, alias: str) -> None:
        alias = " ".join(alias.split())
        if app_name not in self.app_names:
            raise ValueError(f"Unknown catalog app: {app_name}")
        if language not in self.data:
            raise ValueError(f"Unsupported alias language: {language}")
        if not normalize_phrase(alias):
            raise ValueError("Alias cannot be empty")
        owner = self.owner(alias, language)
        if owner is not None and owner != app_name:
            raise ValueError(f"Alias is already assigned to {owner}")
        aliases = self.data[language].setdefault(app_name, [])
        if not any(normalize_phrase(existing) == normalize_phrase(alias) for existing in aliases):
            aliases.append(alias)

    def remove(self, app_name: str, language: str, alias: str) -> None:
        aliases = self.data[language].get(app_name, [])
        normalized = normalize_phrase(alias)
        self.data[language][app_name] = [
            existing for existing in aliases if normalize_phrase(existing) != normalized
        ]
        if not self.data[language][app_name]:
            self.data[language].pop(app_name, None)

    def replace(self, app_name: str, language: str, aliases: list[str]) -> None:
        if app_name not in self.app_names:
            raise ValueError(f"Unknown catalog app: {app_name}")
        if language not in self.data:
            raise ValueError(f"Unsupported alias language: {language}")
        previous = list(self.data[language].get(app_name, []))
        self.data[language].pop(app_name, None)
        try:
            for alias in aliases:
                self.add(app_name, language, alias)
        except Exception:
            if previous:
                self.data[language][app_name] = previous
            raise

    def save(self) -> None:
        for language, path in self.paths.items():
            ordered = {
                app_name: self.data[language][app_name]
                for app_name in sorted(self.data[language], key=str.casefold)
                if self.data[language][app_name]
            }
            atomic_write_text(path, json.dumps(ordered, ensure_ascii=False, indent=2) + "\n")
