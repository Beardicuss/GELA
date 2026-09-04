from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse

from .alias_cleanup import synchronize_alias_files
from .config import USER_CONFIG_ROOT
from .windows_process import hidden_process_kwargs
from .storage import atomic_write_text


CATALOG_PATH = USER_CONFIG_ROOT / "apps.json"
ALIASES_PATH = USER_CONFIG_ROOT / "aliases.json"
PLAYLIST_EXTENSIONS = frozenset({".xspf", ".m3u", ".m3u8", ".pls"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".wma", ".opus"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"})
MEDIA_EXTENSIONS = PLAYLIST_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
MEDIA_ROOTS = (
    Path.home() / "Music" / "Playlists",
    Path.home() / "Music" / "Videos",
    Path.home() / "Pictures",
)


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    aliases: list[str]
    launch_type: str
    launch_value: str
    process_names: list[str] = field(default_factory=list)


def normalize_phrase(value: str) -> str:
    value = value.casefold().replace("™", " ").replace("®", " ")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def executable_process_name(launch_value: str) -> str | None:
    """Return the complete executable stem for a path-like Start entry."""
    if "!" in launch_value or not launch_value.casefold().endswith(".exe"):
        return None
    name = PureWindowsPath(launch_value).stem.strip()
    return name if re.fullmatch(r"[A-Za-z0-9_. -]+", name) else None


def _entry_qualifier(entry: CatalogEntry) -> str:
    value = entry.launch_value
    if entry.launch_type == "file":
        return Path(value).parent.name.strip() or "Media"
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        return parsed.hostname.removeprefix("www.")
    versions = re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)+(?:[A-Za-z]\d+)?", value)
    if versions:
        return versions[0]
    executable = executable_process_name(value)
    if executable:
        parent = PureWindowsPath(value).parent.name.strip()
        if parent and parent.casefold() not in {"bin", "bugreporter", "editor"}:
            return parent
        return executable
    if "!" in value and "_" in value:
        return "Microsoft Store"
    return entry.launch_type.replace("_", " ").title()


def _disambiguate_names(entries: list[CatalogEntry]) -> list[CatalogEntry]:
    """Give same-named launch targets deterministic, spoken-distinct identities."""
    groups: dict[str, list[CatalogEntry]] = {}
    for entry in entries:
        groups.setdefault(normalize_phrase(entry.name), []).append(entry)
    result: list[CatalogEntry] = []
    for group in groups.values():
        if len(group) == 1:
            result.extend(group)
            continue
        used_qualifiers: dict[str, int] = {}
        for entry in sorted(group, key=lambda item: (item.launch_type, item.launch_value.casefold())):
            qualifier = _entry_qualifier(entry)
            normalized_qualifier = normalize_phrase(qualifier)
            occurrence = used_qualifiers.get(normalized_qualifier, 0) + 1
            used_qualifiers[normalized_qualifier] = occurrence
            if occurrence > 1:
                qualifier = f"{qualifier} {occurrence}"
            name = f"{entry.name} ({qualifier})"
            base_alias = normalize_phrase(entry.name)
            aliases = [
                normalize_phrase(name),
                *(alias for alias in entry.aliases if normalize_phrase(alias) != base_alias),
            ]
            result.append(replace(entry, name=name, aliases=list(dict.fromkeys(aliases))))
    return result


def _start_apps() -> list[CatalogEntry]:
    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        **hidden_process_kwargs(),
    )
    raw = json.loads(result.stdout or "[]")
    if isinstance(raw, dict):
        raw = [raw]
    return [
        CatalogEntry(
            name=item["Name"],
            aliases=[normalize_phrase(item["Name"])],
            launch_type="app_id",
            launch_value=item["AppID"],
        )
        for item in raw
        if item.get("Name") and item.get("AppID")
    ]


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        for suffix in ("Steam", "SteamLibrary", "Program Files (x86)/Steam"):
            candidate = Path(f"{drive}:/{suffix}")
            if (candidate / "steamapps").is_dir():
                roots.append(candidate)
    return roots


def _steam_executable_names(game_dir: Path) -> list[str]:
    """Return likely game processes while excluding launch/setup helpers."""
    if not game_dir.is_dir():
        return []
    excluded_parts = {
        "advguide",
        "artbookost",
        "crashpad",
        "easyanticheat",
        "extras",
        "redist",
    }
    excluded_stems = {
        "cefsubprocess",
        "crashpad_handler",
        "easyanticheat_eos_setup",
        "epicwebhelper",
        "parfait_crash_handler",
        "start_protected_game",
        "unitycrashhandler64",
    }
    names: list[str] = []
    for executable in game_dir.rglob("*.exe"):
        relative_parts = {part.casefold() for part in executable.relative_to(game_dir).parts[:-1]}
        stem = executable.stem
        folded = stem.casefold()
        if relative_parts & excluded_parts or folded in excluded_stems or folded.startswith("vc_redist"):
            continue
        if stem not in names:
            names.append(stem)
    return names


def _steam_games() -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    for root in _steam_roots():
        for manifest in (root / "steamapps").glob("appmanifest_*.acf"):
            text = manifest.read_text(encoding="utf-8", errors="replace")
            name_match = re.search(r'"name"\s+"(.+?)"', text)
            id_match = re.search(r'"appid"\s+"(\d+)"', text)
            if not name_match or not id_match or id_match.group(1) == "228980":
                continue
            app_id = id_match.group(1)
            if app_id in seen:
                continue
            seen.add(app_id)
            name = name_match.group(1)
            entries.append(
                CatalogEntry(
                    name=name,
                    aliases=[normalize_phrase(name)],
                    launch_type="uri",
                    launch_value=f"steam://rungameid/{app_id}",
                    process_names=_steam_executable_names(root / "steamapps" / "common" / name),
                )
            )
    return entries


def is_allowed_media_file(path: Path, roots: tuple[Path, ...] = MEDIA_ROOTS) -> bool:
    """Return whether a supported media file is inside a dedicated media root."""
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if not resolved.is_file() or resolved.suffix.casefold() not in MEDIA_EXTENSIONS:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve(strict=True))
            return True
        except (OSError, ValueError, RuntimeError):
            continue
    return False


def _media_files(roots: tuple[Path, ...] | None = None) -> list[CatalogEntry]:
    roots = MEDIA_ROOTS if roots is None else roots
    entries: list[CatalogEntry] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not is_allowed_media_file(path, roots):
                continue
            entries.append(
                CatalogEntry(
                    name=path.stem,
                    aliases=[normalize_phrase(path.stem)],
                    launch_type="file",
                    launch_value=str(path.resolve()),
                )
            )
    return entries


def scan_catalog_with_status(path: Path = CATALOG_PATH) -> tuple[list[CatalogEntry], bool]:
    entries = _start_apps() + _steam_games() + _media_files()
    unique: dict[tuple[str, str], CatalogEntry] = {}
    for entry in entries:
        unique[(entry.launch_type, entry.launch_value)] = entry
    entries = _disambiguate_names(list(unique.values()))
    synchronize_alias_files(
        {entry.name for entry in entries},
        ALIASES_PATH,
        ALIASES_PATH.with_name("english_aliases.json"),
        ALIASES_PATH.with_name("alias_archive.json"),
    )
    custom_aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8")) if ALIASES_PATH.is_file() else {}
    entries = [
        CatalogEntry(
            name=entry.name,
            aliases=list(dict.fromkeys([*entry.aliases, *custom_aliases.get(entry.name, [])])),
            launch_type=entry.launch_type,
            launch_value=entry.launch_value,
            process_names=entry.process_names,
        )
        for entry in entries
    ]
    catalog = sorted(entries, key=lambda entry: (entry.name.casefold(), entry.launch_value.casefold()))
    serialized = json.dumps([asdict(entry) for entry in catalog], ensure_ascii=False, indent=2) + "\n"
    changed = not path.is_file() or path.read_text(encoding="utf-8") != serialized
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, serialized)
    return catalog, changed


def scan_catalog(path: Path = CATALOG_PATH) -> list[CatalogEntry]:
    catalog, _ = scan_catalog_with_status(path)
    return catalog


def load_catalog(path: Path = CATALOG_PATH) -> list[CatalogEntry]:
    if not path.is_file():
        raise FileNotFoundError(f"App catalog is missing. Run 'voice-assistant scan-apps': {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CatalogEntry(**entry) for entry in raw]


def alias_index(entries: list[CatalogEntry]) -> dict[str, CatalogEntry]:
    index: dict[str, CatalogEntry] = {}
    for entry in entries:
        for alias in [entry.name, *entry.aliases]:
            normalized = normalize_phrase(alias)
            if normalized:
                index.setdefault(normalized, entry)
    return index
