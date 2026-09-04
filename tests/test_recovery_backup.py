import json

import pytest

from voice_assistant.recovery_backup import (
    RecoveryBackupError,
    create_recovery_backup,
    read_recovery_backup,
    restore_recovery_backup,
)


def test_encrypted_recovery_round_trip(tmp_path):
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    (source / "mobile").mkdir()
    (source / "mcu").mkdir()
    (source / "config/settings.json").write_text(json.dumps({"language": "ka"}), encoding="utf-8")
    (source / "mobile/paired_devices.json").write_text('{"phone": {}}', encoding="utf-8")
    (source / "mcu/board_token.txt").write_text("secret-board-token", encoding="ascii")
    backup = tmp_path / "backup.gelabackup"

    files = create_recovery_backup("correct horse battery", backup, source)

    assert backup.read_bytes()[:1] != b"{" and b"secret-board-token" not in backup.read_bytes()
    assert files == ["config/settings.json", "mcu/board_token.txt", "mobile/paired_devices.json"]
    restored = tmp_path / "restored"
    restore_recovery_backup("correct horse battery", backup, restored)
    assert (restored / "config/settings.json").read_text(encoding="utf-8") == '{"language": "ka"}'
    assert (restored / "mcu/board_token.txt").read_text(encoding="ascii") == "secret-board-token"


def test_wrong_password_and_tampering_are_rejected(tmp_path):
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    (source / "config/settings.json").write_text("{}", encoding="utf-8")
    backup = tmp_path / "backup.gelabackup"
    create_recovery_backup("correct horse battery", backup, source)

    with pytest.raises(RecoveryBackupError, match="Incorrect password"):
        read_recovery_backup("incorrect password!!", backup)

    damaged = bytearray(backup.read_bytes())
    damaged[-1] ^= 1
    backup.write_bytes(damaged)
    with pytest.raises(RecoveryBackupError, match="damaged"):
        read_recovery_backup("correct horse battery", backup)


def test_short_password_is_rejected(tmp_path):
    with pytest.raises(RecoveryBackupError, match="at least 10"):
        create_recovery_backup("short", tmp_path / "backup.gelabackup", tmp_path)
