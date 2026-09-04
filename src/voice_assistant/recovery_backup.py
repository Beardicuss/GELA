from __future__ import annotations

import base64
from datetime import datetime
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import tempfile
import zipfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import USER_DATA_ROOT


MAGIC = b"GELA-BACKUP\x00\x01"
AAD_CONTEXT = b"Gela encrypted recovery backup v1"
DEFAULT_BACKUP_DIRECTORY = Path("D:/Gela Backups")
MAX_SOURCE_FILE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
BACKUP_PATHS = (
    "config/settings.json",
    "config/aliases.json",
    "config/english_aliases.json",
    "config/alias_archive.json",
    "config/app_profiles.json",
    "config/routines.json",
    "config/learned_process_targets.json",
    "mobile/paired_devices.json",
    "mobile/bridge_id.txt",
    "mcu/board_token.txt",
)


class RecoveryBackupError(RuntimeError):
    pass


def _derive_key(password: str, salt: bytes) -> bytes:
    if len(password) < 10:
        raise RecoveryBackupError("Use a recovery password with at least 10 characters.")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def _zip_payload(data_root: Path) -> tuple[bytes, list[str]]:
    manifest: dict[str, str] = {}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in BACKUP_PATHS:
            source = data_root / relative
            if not source.is_file():
                continue
            content = source.read_bytes()
            if len(content) > MAX_SOURCE_FILE_BYTES:
                raise RecoveryBackupError(f"Recovery file is unexpectedly large: {relative}")
            archive.writestr(relative, content)
            manifest[relative] = hashlib.sha256(content).hexdigest()
        metadata = {
            "formatVersion": 1,
            "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "files": manifest,
        }
        archive.writestr("manifest.json", json.dumps(metadata, indent=2).encode("utf-8"))
    payload = buffer.getvalue()
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise RecoveryBackupError("Recovery archive exceeds its safety limit.")
    return payload, sorted(manifest)


def create_recovery_backup(password: str, destination: Path, data_root: Path = USER_DATA_ROOT) -> list[str]:
    plaintext, files = _zip_payload(data_root)
    salt, nonce = os.urandom(16), os.urandom(12)
    header = json.dumps(
        {
            "formatVersion": 1,
            "cipher": "AES-256-GCM",
            "kdf": "scrypt",
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "n": 2**15,
            "r": 8,
            "p": 1,
        },
        separators=(",", ":"),
    ).encode("ascii")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    ciphertext = AESGCM(_derive_key(password, salt)).encrypt(nonce, plaintext, AAD_CONTEXT + prefix)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".creating")
    try:
        temporary.write_bytes(prefix + ciphertext)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return files


def default_backup_path(directory: Path = DEFAULT_BACKUP_DIRECTORY) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return directory / f"Gela-Recovery-{stamp}.gelabackup"


def _decrypt(password: str, source: Path) -> bytes:
    content = source.read_bytes()
    minimum = len(MAGIC) + 4 + 16
    if len(content) < minimum or not content.startswith(MAGIC):
        raise RecoveryBackupError("This is not a supported Gela recovery backup.")
    header_length = struct.unpack(">I", content[len(MAGIC) : len(MAGIC) + 4])[0]
    header_start = len(MAGIC) + 4
    header_end = header_start + header_length
    if header_length > 4096 or header_end >= len(content):
        raise RecoveryBackupError("The recovery backup header is invalid.")
    try:
        header = json.loads(content[header_start:header_end].decode("ascii"))
        salt = base64.b64decode(header["salt"], validate=True)
        nonce = base64.b64decode(header["nonce"], validate=True)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RecoveryBackupError("The recovery backup header is invalid.") from exc
    if header.get("formatVersion") != 1 or header.get("n") != 2**15 or len(salt) != 16 or len(nonce) != 12:
        raise RecoveryBackupError("The recovery backup parameters are unsupported.")
    prefix = content[:header_end]
    try:
        return AESGCM(_derive_key(password, salt)).decrypt(nonce, content[header_end:], AAD_CONTEXT + prefix)
    except InvalidTag as exc:
        raise RecoveryBackupError("Incorrect password or damaged recovery backup.") from exc


def read_recovery_backup(password: str, source: Path) -> dict[str, bytes]:
    plaintext = _decrypt(password, source)
    if len(plaintext) > MAX_ARCHIVE_BYTES:
        raise RecoveryBackupError("Decrypted recovery archive exceeds its safety limit.")
    try:
        with zipfile.ZipFile(BytesIO(plaintext), "r") as archive:
            names = archive.namelist()
            allowed = {*BACKUP_PATHS, "manifest.json"}
            if len(names) != len(set(names)) or any(name not in allowed for name in names):
                raise RecoveryBackupError("Recovery backup contains an unexpected path.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            expected = manifest.get("files", {})
            if not isinstance(expected, dict) or set(expected) != set(names) - {"manifest.json"}:
                raise RecoveryBackupError("Recovery manifest does not match its files.")
            result: dict[str, bytes] = {}
            for name, digest in expected.items():
                info = archive.getinfo(name)
                if info.file_size > MAX_SOURCE_FILE_BYTES:
                    raise RecoveryBackupError(f"Recovery file is too large: {name}")
                content = archive.read(name)
                if not isinstance(digest, str) or not hashlib.sha256(content).hexdigest() == digest:
                    raise RecoveryBackupError(f"Recovery integrity check failed: {name}")
                result[name] = content
            return result
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        if isinstance(exc, RecoveryBackupError):
            raise
        raise RecoveryBackupError("Recovery backup content is invalid.") from exc


def restore_recovery_backup(password: str, source: Path, data_root: Path = USER_DATA_ROOT) -> list[str]:
    files = read_recovery_backup(password, source)
    with tempfile.TemporaryDirectory(prefix="gela-restore-") as temporary_name:
        temporary_root = Path(temporary_name)
        for relative, content in files.items():
            staged = temporary_root / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
        for relative in sorted(files):
            staged = temporary_root / relative
            destination = data_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            replacement = destination.with_name(destination.name + ".restoring")
            replacement.write_bytes(staged.read_bytes())
            os.replace(replacement, destination)
    return sorted(files)
