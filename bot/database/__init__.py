"""
Database package — Phase 0.2.

Public surface
--------------
DatabaseManager     Singleton async engine + session factory (connection.py).
Base                SQLAlchemy DeclarativeBase (base.py).
BaseModel           Abstract ORM base with id / created_at / updated_at (base.py).
get_session         Async context manager yielding a committed session (session.py).

ORM models (database/models/)
    UserORM, RoleORM, PackageORM, ServerORM, VPNKeyORM, OrderORM,
    WalletORM, TransactionORM, ReferralORM, FreeTrialORM,
    SettingORM, NotificationORM, AuditLogORM

Repositories (database/repositories/)
    UserRepository, PackageRepository, ServerRepository, VPNKeyRepository,
    WalletRepository, OrderRepository, GrowthRepository,
    SettingsRepository, NotificationRepository

Initialisation (called once in main.py)
-----------------------------------------
    from database import DatabaseManager
    db = DatabaseManager.initialise(settings.database_url)
    await db.init()   # creates engine + runs create_all() for every model

NOTE: All ORM models are imported below so that Base.metadata is populated
before DatabaseManager.init() calls create_all().  Never remove these imports.
"""

from database.base import Base, BaseModel
from database.connection import DatabaseManager
from database.session import get_session

# ── Import every ORM model so Base.metadata discovers all tables ──────────────
# This must happen before DatabaseManager.init() → create_all() is called.
import database.models  # noqa: F401  (side-effect import — registers all models)

__all__ = [
    "Base",
    "BaseModel",
    "DatabaseManager",
    "get_session",
]
