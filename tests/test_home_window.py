from __future__ import annotations

import json

from voice_assistant import home_window


def test_configured_home_bundle_is_discovered(tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "Gela-Home"
    (bundle / ".next" / "static").mkdir(parents=True)
    (bundle / "server.js").write_text("", encoding="utf-8")
    config = tmp_path / "bundle_path.json"
    config.write_text(json.dumps({"path": str(bundle)}), encoding="utf-8")
    monkeypatch.setattr(home_window, "SOURCE_BUNDLE", tmp_path / "missing")

    assert home_window.find_home_bundle(config) == bundle


def test_invalid_home_bundle_is_not_offered(tmp_path, monkeypatch) -> None:
    config = tmp_path / "bundle_path.json"
    config.write_text(json.dumps({"path": str(tmp_path / "missing")}), encoding="utf-8")
    monkeypatch.setattr(home_window, "SOURCE_BUNDLE", tmp_path / "missing")

    assert home_window.find_home_bundle(config) is None
