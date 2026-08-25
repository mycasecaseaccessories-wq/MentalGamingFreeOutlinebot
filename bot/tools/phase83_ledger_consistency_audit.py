"""Independent Phase 8.3 ledger consistency audit for a local database."""
from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal

from sqlalchemy import select

from database.connection import DatabaseManager
from database.models.transaction import TransactionORM
from database.models.wallet import WalletORM


async def main() -> int:
    database_url = os.environ.get("BOT_DATABASE_URL")
    if not database_url:
        sys.stdout.write("LEDGER_AUDIT = NOT_EXECUTED (BOT_DATABASE_URL is unset)\n")
        return 2
    db = DatabaseManager(database_url)
    await db.init()
    mismatches: list[str] = []
    async with db.session() as session:
        wallets = (await session.execute(select(WalletORM))).scalars().all()
        for wallet in wallets:
            rows = (
                await session.execute(
                    select(TransactionORM.amount).where(
                        TransactionORM.wallet_id == wallet.id
                    )
                )
            ).scalars().all()
            ledger_sum = sum((Decimal(str(amount)) for amount in rows), Decimal("0"))
            balance = Decimal(str(wallet.balance))
            if ledger_sum != balance:
                mismatches.append(
                    f"wallet_id={wallet.id} balance={balance} ledger_sum={ledger_sum}"
                )
    await db.close()
    if mismatches:
        sys.stdout.write("LEDGER_AUDIT = FAIL\n")
        sys.stdout.write("\n".join(mismatches) + "\n")
        return 1
    sys.stdout.write(f"LEDGER_AUDIT = PASS ({len(wallets)} wallets checked)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


