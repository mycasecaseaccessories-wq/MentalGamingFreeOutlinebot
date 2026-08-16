"""Phase 3.1 server domain and admin state-boundary tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.services.server_service import ServerService
from database.connection import DatabaseManager
from database.models.server import ServerORM
from database.models.user import UserORM


async def _db(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'server31.db'}")
    await db.init()
    async with db.session() as session:
        session.add_all([
            UserORM(telegram_id=881001, full_name="Server Admin", role="admin", language="en", is_active=True, is_verified=True),
            UserORM(telegram_id=881002, full_name="Normal User", role="customer", language="my", is_active=True, is_verified=True),
        ])
    return db


@pytest.mark.asyncio
async def test_manual_registration_starts_unknown_and_disabled_without_connectivity(tmp_path):
    db = await _db(tmp_path)
    service = ServerService(db)
    result = await service.register_manual(actor_telegram_id=881001, name="MG-SG-01", host="vpn-sg.example.com", country_code="sg", region="Singapore", notes="metadata only")
    assert result.is_success
    item = result.unwrap().server
    assert item.public_server_id.startswith("SRV-")
    assert item.status == ServerORM.STATUS_UNKNOWN
    assert item.health_status == ServerORM.HEALTH_UNKNOWN
    assert item.enabled is False
    async with db.session() as session:
        row = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == item.public_server_id))).scalar_one()
        assert row.api_url is None
        assert row.cert_sha256 is None
        assert row.provider_server_id is None
        assert row.enabled is False
        assert row.is_active is False
    await db.close()


@pytest.mark.asyncio
async def test_unknown_server_cannot_be_enabled_and_non_admin_cannot_mutate(tmp_path):
    db = await _db(tmp_path)
    service = ServerService(db)
    created = await service.register_manual(actor_telegram_id=881001, name="MG-JP-01")
    public_id = created.unwrap().server.public_server_id
    assert (await service.set_enabled(actor_telegram_id=881001, public_server_id=public_id, enabled=True)).error.code == "server_not_verified"
    assert (await service.set_enabled(actor_telegram_id=881002, public_server_id=public_id, enabled=False)).error.code == "unauthorized"
    await db.close()


@pytest.mark.asyncio
async def test_disable_maintenance_and_archive_are_state_safe(tmp_path):
    db = await _db(tmp_path)
    service = ServerService(db)
    created = await service.register_manual(actor_telegram_id=881001, name="MG-US-01")
    public_id = created.unwrap().server.public_server_id
    maintenance = await service.set_maintenance(actor_telegram_id=881001, public_server_id=public_id, maintenance=True)
    assert maintenance.is_success
    assert maintenance.unwrap().server.status == ServerORM.STATUS_MAINTENANCE
    restored = await service.set_maintenance(actor_telegram_id=881001, public_server_id=public_id, maintenance=False)
    assert restored.is_success
    assert restored.unwrap().server.status == ServerORM.STATUS_DISABLED
    archived = await service.archive(actor_telegram_id=881001, public_server_id=public_id)
    assert archived.is_success
    assert archived.unwrap().server.status == ServerORM.STATUS_ARCHIVED
    assert archived.unwrap().server.enabled is False
    assert (await service.update_metadata(actor_telegram_id=881001, public_server_id=public_id, name="MG-US-ARCHIVED")).error.code == "archived"
    await db.close()


@pytest.mark.asyncio
async def test_server_listing_paginates_and_hides_archived_by_default(tmp_path):
    db = await _db(tmp_path)
    service = ServerService(db)
    first = await service.register_manual(actor_telegram_id=881001, name="MG-01")
    second = await service.register_manual(actor_telegram_id=881001, name="MG-02")
    await service.archive(actor_telegram_id=881001, public_server_id=first.unwrap().server.public_server_id)
    page = await service.list_servers(page=1, page_size=1)
    assert page.total == 1
    assert page.items[0].public_server_id == second.unwrap().server.public_server_id
    all_rows = await service.list_servers(page=1, page_size=10, include_archived=True)
    assert all_rows.total == 2
    await db.close()
