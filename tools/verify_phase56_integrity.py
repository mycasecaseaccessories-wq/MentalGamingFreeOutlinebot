import asyncio
import os
import tempfile
from pathlib import Path

from sqlalchemy import text

from database.connection import DatabaseManager


async def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        DatabaseManager._instance = None
        db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{Path(directory) / 'integrity.db'}")
        await db.init()
        async with db.session() as session:
            head = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
            rate_table = (await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='free_trial_rate_limits'"))).scalar_one()
            upgrade_fks = (await session.execute(text("PRAGMA foreign_key_list('free_trial_upgrades')"))).all()
            restriction_fks = (await session.execute(text("PRAGMA foreign_key_list('free_trial_restrictions')"))).all()
            offer_fks = (await session.execute(text("PRAGMA foreign_key_list('free_trial_upgrade_offers')"))).all()
        assert head == "0027_phase56_integrity_and_rate_limits"
        assert rate_table == "free_trial_rate_limits"
        assert len(upgrade_fks) == 6
        assert len(restriction_fks) == 2
        assert len(offer_fks) == 1
        await db.close()
        print("phase56 integrity schema: OK")


if __name__ == "__main__":
    os.environ.setdefault("BOT_TOKEN", "phase56-test-token")
    os.environ.setdefault("SESSION_SECRET", "phase56-test-secret")
    asyncio.run(main())
