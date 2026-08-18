"""Phase 7.4 backup lifecycle; Telegram handlers must delegate here."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.services.base import BaseService
from app.events import EventType, bus
from database.models.backup_record import BackupRecordORM, BackupStatus, BackupType, RestoreTestStatus
from app.services.backup_provider import BackupProviderError, NativeBackupProvider
from app.services.maintenance_service import MaintenanceService, MaintenanceBlockedError


class BackupService(BaseService):
    """Durable backup metadata plus database-native artifact operations."""

    RETENTION_DAYS = {"hourly": 2, "daily": 30, "weekly": 84, "monthly": 366, "emergency": 730}

    def __init__(self, db=None, *, provider: NativeBackupProvider | None = None, database_url: str | None = None, maintenance_service: MaintenanceService | None = None) -> None:
        super().__init__(db)
        self.database_url = database_url or getattr(db, "_database_url", "")
        self.provider = provider or NativeBackupProvider()
        self.maintenance_service = maintenance_service

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _expiry(self, retention_class: str, now: datetime) -> datetime:
        days = self.RETENTION_DAYS.get(retention_class, self.RETENTION_DAYS["daily"])
        return now + timedelta(days=days)

    async def create_backup(
        self,
        *,
        backup_type: BackupType | str = BackupType.AUTOMATIC,
        retention_class: str = "daily",
        created_by: int | None = None,
        job_id: int | None = None,
    ) -> dict:
        if self.maintenance_service is not None:
            try:
                await self.maintenance_service.assert_operation_allowed("backup", "CREATE")
            except MaintenanceBlockedError:
                return {"status": BackupStatus.FAILED.value, "safe_error_code": "maintenance_active"}
        backup_type_value = backup_type.value if isinstance(backup_type, BackupType) else str(backup_type)
        public_id = f"bkp_{uuid.uuid4().hex[:24]}"
        now = self._now()
        async with self.db.session() as session:
            row = BackupRecordORM(
                public_id=public_id,
                backup_type=backup_type_value,
                database_engine=self.provider.engine(self.database_url),
                status=BackupStatus.RUNNING.value,
                verification_status=BackupStatus.PENDING.value,
                restore_test_status=RestoreTestStatus.NOT_RUN.value,
                retention_class=retention_class,
                expires_at=self._expiry(retention_class, now),
                started_at=now,
                created_by=created_by,
                job_id=job_id,
                manifest_json=json.dumps({"rpo_target_minutes": 15, "rto_target_minutes": 60}),
            )
            session.add(row)
            await session.flush()
            record_id = row.id
        try:
            artifact = self.provider.create(self.database_url, public_id=public_id)
            manifest = {
                "database_engine": artifact.database_engine,
                "storage_provider": self.provider.provider_name,
                "storage_reference": str(artifact.path),
                "size_bytes": artifact.size_bytes,
                "checksum": artifact.checksum,
                "checksum_algorithm": "sha256",
                "encrypted": artifact.encrypted,
                "encryption_key_version": artifact.encryption_key_version,
            }
            async with self.db.session() as session:
                row = await session.get(BackupRecordORM, record_id)
                row.status = BackupStatus.COMPLETED.value
                row.completed_at = self._now()
                row.size_bytes = artifact.size_bytes
                row.checksum = artifact.checksum
                row.encrypted = artifact.encrypted
                row.encryption_key_version = artifact.encryption_key_version
                row.storage_provider = self.provider.provider_name
                row.storage_reference = str(artifact.path)
                row.verification_status = BackupStatus.PENDING.value
                row.manifest_json = json.dumps(manifest, sort_keys=True)
            verified = await self.verify_backup(public_id)
            await bus.emit(EventType.BACKUP_CREATED, public_id=public_id, status=verified.get("status"), database_engine=artifact.database_engine)
            return verified
        except BackupProviderError as exc:
            async with self.db.session() as session:
                row = await session.get(BackupRecordORM, record_id)
                row.status = BackupStatus.FAILED.value
                row.safe_error_code = exc.code
                row.completed_at = self._now()
            await bus.emit(EventType.BACKUP_FAILED, public_id=public_id, safe_error_code=exc.code)
            return {"public_id": public_id, "status": BackupStatus.FAILED.value, "safe_error_code": exc.code}
        except Exception:
            async with self.db.session() as session:
                row = await session.get(BackupRecordORM, record_id)
                row.status = BackupStatus.FAILED.value
                row.safe_error_code = "backup_unexpected_failure"
                row.completed_at = self._now()
            await bus.emit(EventType.BACKUP_FAILED, public_id=public_id, safe_error_code="backup_unexpected_failure")
            return {"public_id": public_id, "status": BackupStatus.FAILED.value, "safe_error_code": "backup_unexpected_failure"}

    async def verify_backup(self, public_id: str) -> dict:
        async with self.db.session() as session:
            row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one_or_none()
            if row is None:
                return {"public_id": public_id, "status": BackupStatus.FAILED.value, "safe_error_code": "backup_not_found"}
            row.status = BackupStatus.VERIFYING.value
            storage_reference = row.storage_reference
            expected = row.checksum
            engine = row.database_engine
        try:
            if not storage_reference or not Path(storage_reference).exists():
                raise BackupProviderError("backup_artifact_missing")
            data = Path(storage_reference).read_bytes()
            actual = hashlib.sha256(data).hexdigest()
            if expected and actual != expected:
                raise BackupProviderError("backup_checksum_mismatch")
            if engine == "sqlite":
                decrypted = self.provider.open_decrypted(storage_reference)
                try:
                    conn = sqlite3.connect(str(decrypted))
                    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
                    conn.close()
                finally:
                    decrypted.unlink(missing_ok=True)
                if result != "ok":
                    raise BackupProviderError("sqlite_integrity_check_failed")
            async with self.db.session() as session:
                row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one()
                row.status = BackupStatus.VERIFIED.value
                row.verification_status = BackupStatus.VERIFIED.value
                row.verified_at = self._now()
            await bus.emit(EventType.BACKUP_VERIFIED, public_id=public_id, checksum=actual)
            return {"public_id": public_id, "status": BackupStatus.VERIFIED.value, "checksum": actual, "restore_test_status": row.restore_test_status}
        except BackupProviderError as exc:
            async with self.db.session() as session:
                row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one_or_none()
                if row:
                    row.status = BackupStatus.CORRUPTED.value
                    row.verification_status = BackupStatus.CORRUPTED.value
                    row.safe_error_code = exc.code
            return {"public_id": public_id, "status": BackupStatus.CORRUPTED.value, "safe_error_code": exc.code}

    async def list_backups(self, *, limit: int = 100, statuses: tuple[str, ...] | None = None) -> list[dict]:
        async with self.db.session() as session:
            query = select(BackupRecordORM).order_by(BackupRecordORM.created_at.desc()).limit(max(1, min(limit, 500)))
            if statuses:
                query = query.where(BackupRecordORM.status.in_(statuses))
            rows = list((await session.execute(query)).scalars().all())
        return [self._safe_row(row) for row in rows]

    async def get_backup(self, public_id: str) -> dict | None:
        async with self.db.session() as session:
            row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one_or_none()
        return self._safe_row(row) if row else None

    async def apply_retention(self, *, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
        now = now or self._now()
        deleted = 0
        async with self.db.session() as session:
            rows = list((await session.execute(select(BackupRecordORM).where(BackupRecordORM.expires_at <= now, BackupRecordORM.status.in_((BackupStatus.VERIFIED.value, BackupStatus.CORRUPTED.value, BackupStatus.FAILED.value))).limit(limit))).scalars().all())
            for row in rows:
                if row.storage_reference:
                    self.provider.delete(row.storage_reference)
                row.status = BackupStatus.DELETED.value
                deleted += 1
        await bus.emit(EventType.BACKUP_RETENTION_APPLIED, deleted=deleted)
        return {"deleted": deleted}

    async def prepare_restore(self, public_id: str, *, actor_user_id: int, production: bool = False) -> dict:
        record = await self.get_backup(public_id)
        if not record:
            return {"allowed": False, "safe_error_code": "backup_not_found"}
        if record["status"] != BackupStatus.VERIFIED.value:
            return {"allowed": False, "safe_error_code": "backup_not_verified"}
        await bus.emit(EventType.BACKUP_RESTORE_PREPARED, public_id=public_id, actor_user_id=actor_user_id, production=production)
        return {
            "allowed": True,
            "mode": "production" if production else "staging",
            "requires_second_admin": production,
            "public_id": public_id,
            "actor_user_id": actor_user_id,
            "pre_restore_snapshot_required": production,
            "maintenance_lock_required": production,
            "post_restore_reconciliation_required": True,
        }

    async def verify_restore(self, public_id: str) -> dict:
        async with self.db.session() as session:
            record_row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one_or_none()
        if record_row is None or record_row.status != BackupStatus.VERIFIED.value:
            return {"public_id": public_id, "status": RestoreTestStatus.FAILED.value, "safe_error_code": "backup_not_verified"}
        record = self._safe_row(record_row)
        if record_row.database_engine != "sqlite":
            return {"public_id": public_id, "status": RestoreTestStatus.FAILED.value, "safe_error_code": "isolated_restore_not_supported"}
        decrypted = self.provider.open_decrypted(record_row.storage_reference)
        try:
            conn = sqlite3.connect(str(decrypted))
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            conn.close()
            required = {"users", "orders", "wallets", "vpn_keys", "backup_records"}
            if integrity != "ok" or not required.issubset(tables):
                raise BackupProviderError("restore_integrity_failed")
        except BackupProviderError as exc:
            status, code = RestoreTestStatus.FAILED.value, exc.code
        else:
            status, code = RestoreTestStatus.PASSED.value, None
        finally:
            decrypted.unlink(missing_ok=True)
        async with self.db.session() as session:
            row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == public_id))).scalar_one()
            row.restore_test_status = status
            row.restore_tested_at = self._now()
            if code:
                row.safe_error_code = code
        await bus.emit(EventType.BACKUP_RESTORE_TESTED, public_id=public_id, status=status, safe_error_code=code)
        return {"public_id": public_id, "status": status, "safe_error_code": code, "reconciliation_required": True}

    async def run_latest_restore_test(self) -> dict:
        async with self.db.session() as session:
            row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.status == BackupStatus.VERIFIED.value).order_by(BackupRecordORM.created_at.desc()).limit(1))).scalar_one_or_none()
        if row is None:
            return {"status": RestoreTestStatus.FAILED.value, "safe_error_code": "no_verified_backup"}
        return await self.verify_restore(row.public_id)

    async def post_restore_reconciliation_report(self) -> dict:
        """Return an explicit report boundary; destructive repair is never implicit."""
        return {
            "status": "report_only",
            "outline": {"status": "requires_remote_comparison", "repair": "admin_approved_only"},
            "payments": {"status": "requires_provider_comparison", "repair": "idempotency_and_admin_review"},
            "wallets": {"status": "requires_ledger_comparison", "repair": "no_blind_overwrite"},
            "rewards_entitlements": {"status": "requires_idempotency_replay_check", "repair": "authoritative_provider_only"},
            "background_jobs": {"status": "leases_must_be_recovered", "repair": "durable_job_recovery"},
        }

    @staticmethod
    def _safe_row(row: BackupRecordORM) -> dict:
        return {
            "public_id": row.public_id,
            "backup_type": row.backup_type,
            "database_engine": row.database_engine,
            "status": row.status,
            "storage_provider": row.storage_provider,
            "size_bytes": row.size_bytes,
            "checksum": row.checksum,
            "encrypted": row.encrypted,
            "verification_status": row.verification_status,
            "restore_test_status": row.restore_test_status,
            "retention_class": row.retention_class,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "safe_error_code": row.safe_error_code,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
