"""Launch one current, allowlisted Gela catalog item from Gela Home.

The browser passes only a digest. This process re-reads the current catalog and
uses Gela's existing verified launcher; it never accepts a path or command line
from the browser.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath

from .catalog import CatalogEntry, load_catalog
from .launcher import launch_verified
from .storage import atomic_write_text


KINDS = frozenset({"apps", "games", "media", "browsers"})
BROWSER_NAMES = re.compile(
    r"\b(chrome|edge|firefox|brave|opera|vivaldi|chromium|waterfox|librewolf|tor browser|arc)\b",
    re.IGNORECASE,
)


def is_browser(entry: CatalogEntry) -> bool:
    if entry.launch_type != "app_id":
        return False
    target = entry.launch_value.strip().casefold()
    executable = PureWindowsPath(target).name.removesuffix(".exe")
    return bool(BROWSER_NAMES.search(entry.name)) or executable in {
        "chrome", "msedge", "firefox", "brave", "brave-browser", "opera",
        "vivaldi", "chromium", "waterfox", "librewolf", "arc",
    }


def kind_for(entry: CatalogEntry) -> str | None:
    if entry.launch_type == "file":
        return "media"
    if entry.launch_type == "uri" and entry.launch_value.casefold().startswith(
        "steam://rungameid/"
    ):
        return "games"
    if is_browser(entry):
        return "browsers"
    if entry.launch_type == "app_id":
        return "apps"
    return None


def entry_id(entry: CatalogEntry) -> str:
    identity = f"{entry.launch_type}\0{entry.launch_value}\0{entry.name}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def find_entry(kind: str, item_id: str, entries: list[CatalogEntry]) -> CatalogEntry:
    if kind not in KINDS or len(item_id) != 24 or any(c not in "0123456789abcdef" for c in item_id):
        raise ValueError("Invalid catalog selection")
    matches = [
        entry
        for entry in entries
        if (kind_for(entry) == kind or (kind == "apps" and entry.launch_type == "app_id"))
        if entry_id(entry) == item_id
    ]
    if len(matches) != 1:
        raise ValueError("Catalog item is unavailable or changed")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in (2, 3):
        if sys.stdout is not None:
            print(json.dumps({"ok": False, "error": "Expected a catalog category and ID"}))
        return 2
    try:
        entry = find_entry(args[0], args[1], load_catalog())
        detail = launch_verified(entry)
        result = {"ok": True, "name": entry.name, "detail": detail}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False) + "\n"
    if len(args) == 3:
        atomic_write_text(Path(args[2]), payload)
    elif sys.stdout is not None:
        print(payload, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
