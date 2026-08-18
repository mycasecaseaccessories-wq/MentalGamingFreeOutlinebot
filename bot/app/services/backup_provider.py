"""Database-native backup providers and encrypted artifact handling."""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken


class BackupProviderError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True, slots=True)
class BackupArtifact:
    path: Path
    size_bytes: int
    checksum: str
    encrypted: bool
    encryption_key_version: str | None
    database_engine: str


class BackupCrypto:
    """Encrypt artifacts only when a valid Fernet key is configured."""

    def __init__(self) -> None:
        raw = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
        self.key_version = os.getenv("BACKUP_ENCRYPTION_KEY_VERSION", "v1").strip() or "v1"
        self.required = os.getenv("BACKUP_REQUIRE_ENCRYPTION", "0").lower() in {"1", "true", "yes"}
        self._fernet: Fernet | None = None
        if raw:
            try:
                self._fernet = Fernet(raw.encode("ascii"))
            except Exception as exc:
                raise BackupProviderError("invalid_encryption_key", "Configured backup key is invalid") from exc
        elif self.required:
            raise BackupProviderError("encryption_key_unavailable", "Encrypted backups are required but no key is configured")

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def protect(self, source: Path, destination: Path) -> None:
        if self._fernet is None:
            shutil.copyfile(source, destination)
            return
        destination.write_bytes(self._fernet.encrypt(source.read_bytes()))

    def unprotect(self, source: Path, destination: Path) -> None:
        if self._fernet is None:
            shutil.copyfile(source, destination)
            return
        try:
            destination.write_bytes(self._fernet.decrypt(source.read_bytes()))
        except InvalidToken as exc:
            raise BackupProviderError("backup_decryption_failed", "Backup could not be decrypted") from exc


class NativeBackupProvider:
    """Use the database engine's safe/native backup mechanism."""

    provider_name = "native-local"

    def __init__(self, root: str | Path | None = None, *, crypto: BackupCrypto | None = None) -> None:
        self.root = Path(root or os.getenv("BACKUP_ROOT", "./data/backups")).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.crypto = crypto or BackupCrypto()

    @staticmethod
    def engine(database_url: str) -> str:
        lowered = database_url.lower()
        if lowered.startswith("sqlite"):
            return "sqlite"
        if "postgres" in lowered:
            return "postgresql"
        if lowered.startswith("mysql") or "mariadb" in lowered:
            return "mysql"
        return "unknown"

    def create(self, database_url: str, *, public_id: str) -> BackupArtifact:
        engine = self.engine(database_url)
        if engine == "unknown":
            raise BackupProviderError("unsupported_database_engine", "Database engine is not supported")
        with tempfile.TemporaryDirectory(prefix=f"backup-{public_id}-", dir=self.root) as tmp:
            raw = Path(tmp) / "database.dump"
            if engine == "sqlite":
                self._sqlite_backup(database_url, raw)
            elif engine == "postgresql":
                self._native_dump(["pg_dump", "--format=custom", "--file", str(raw), database_url], raw)
            else:
                self._native_dump(["mysqldump", "--single-transaction", "--routines", "--triggers", database_url, "--result-file", str(raw)], raw)
            target = self.root / f"{public_id}.backup"
            self.crypto.protect(raw, target)
        data = target.read_bytes()
        return BackupArtifact(target, len(data), hashlib.sha256(data).hexdigest(), self.crypto.enabled, self.crypto.key_version if self.crypto.enabled else None, engine)

    @staticmethod
    def _sqlite_backup(database_url: str, destination: Path) -> None:
        parsed = urlparse(database_url.replace("sqlite+aiosqlite", "sqlite", 1))
        source = Path(parsed.path)
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.exists():
            raise BackupProviderError("database_not_found", "SQLite database file was not found")
        source_conn = sqlite3.connect(str(source))
        destination_conn = sqlite3.connect(str(destination))
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
            source_conn.close()

    @staticmethod
    def _native_dump(command: list[str], destination: Path) -> None:
        try:
            completed = subprocess.run(command, capture_output=True, timeout=300, check=False)
        except FileNotFoundError as exc:
            raise BackupProviderError("backup_tool_unavailable", "Native database backup tool is unavailable") from exc
        if completed.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
            raise BackupProviderError("native_backup_failed", "Native database backup failed")

    def open_decrypted(self, artifact_path: str | Path) -> Path:
        source = Path(artifact_path)
        if not source.exists():
            raise BackupProviderError("backup_not_found", "Backup artifact was not found")
        fd, name = tempfile.mkstemp(prefix="restore-", suffix=".dump", dir=self.root)
        os.close(fd)
        target = Path(name)
        self.crypto.unprotect(source, target)
        return target

    def delete(self, storage_reference: str) -> None:
        path = Path(storage_reference)
        if path.exists() and path.is_file() and path.parent == self.root:
            path.unlink()
