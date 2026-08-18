from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.services.backup_provider import NativeBackupProvider
from app.services.backup_service import BackupService
from database.connection import DatabaseManager
from database.models.backup_record import BackupRecordORM, BackupStatus, RestoreTestStatus


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'phase74.db'}"


async def _service(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    provider = NativeBackupProvider(tmp_path / "backups")
    return db, BackupService(db, provider=provider, database_url=_url(tmp_path))


@pytest.mark.asyncio
async def test_sqlite_backup_is_verified_and_restore_tested(tmp_path):
    db, service = await _service(tmp_path)
    result = await service.create_backup(backup_type="manual", retention_class="daily", created_by=992001)
    assert result["status"] == BackupStatus.VERIFIED.value
    restore = await service.verify_restore(result["public_id"])
    assert restore["status"] == RestoreTestStatus.PASSED.value
    record = await service.get_backup(result["public_id"])
    assert record["verification_status"] == BackupStatus.VERIFIED.value
    assert record["restore_test_status"] == RestoreTestStatus.PASSED.value
    await db.close()


@pytest.mark.asyncio
async def test_checksum_corruption_is_not_reported_healthy(tmp_path):
    db, service = await _service(tmp_path)
    result = await service.create_backup(backup_type="manual")
    async with db.session() as session:
        row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == result["public_id"]))).scalar_one()
        path = Path(row.storage_reference)
        path.write_bytes(path.read_bytes() + b"corrupted")
    verified = await service.verify_backup(result["public_id"])
    assert verified["status"] == BackupStatus.CORRUPTED.value
    assert verified["safe_error_code"] == "backup_checksum_mismatch"
    await db.close()


@pytest.mark.asyncio
async def test_retention_deletes_expired_artifact_and_keeps_metadata_state(tmp_path):
    db, service = await _service(tmp_path)
    result = await service.create_backup(backup_type="manual", retention_class="daily")
    async with db.session() as session:
        row = (await session.execute(select(BackupRecordORM).where(BackupRecordORM.public_id == result["public_id"]))).scalar_one()
        row.expires_at = service._now()
        path = Path(row.storage_reference)
    retention = await service.apply_retention()
    assert retention["deleted"] == 1
    assert not path.exists()
    record = await service.get_backup(result["public_id"])
    assert record["status"] == BackupStatus.DELETED.value
    await db.close()


@pytest.mark.asyncio
async def test_restore_preparation_requires_production_safety_and_reconciliation(tmp_path):
    db, service = await _service(tmp_path)
    result = await service.create_backup(backup_type="manual")
    staging = await service.prepare_restore(result["public_id"], actor_user_id=992001, production=False)
    production = await service.prepare_restore(result["public_id"], actor_user_id=992001, production=True)
    assert staging["allowed"] is True and staging["requires_second_admin"] is False
    assert production["allowed"] is True
    assert production["requires_second_admin"] is True
    assert production["maintenance_lock_required"] is True
    report = await service.post_restore_reconciliation_report()
    assert report["status"] == "report_only"
    assert report["outline"]["repair"] == "admin_approved_only"
    assert report["payments"]["repair"] == "idempotency_and_admin_review"
    await db.close()
