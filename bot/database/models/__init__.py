"""
ORM models package.

Every module here defines one or more SQLAlchemy mapped classes that
correspond to database tables.  All models inherit from BaseModel to
guarantee standard primary key and audit timestamp columns.

Import all models here so that Base.metadata knows about every table
when DatabaseManager.init() calls create_all().

Table inventory
---------------
users              Core user accounts (telegram_id, role, language, …)
user_preferences   Per-user configurable preferences (language, tz, theme, …)
roles              Role definitions and permission bitfields
packages           VPN subscription packages (name, price, duration, …)
servers            Outline VPN server instances (api_url, cert, region, …)
vpn_keys           Issued Outline access keys linked to users and servers
orders             Purchase orders linking users to packages
wallets            Per-user wallet balances
transactions       Wallet debit/credit ledger entries
referrals          Referral relationships between users
free_trials        Free trial allocations and usage tracking
settings           Key-value platform configuration store
notifications      Scheduled or sent notification records
audit_logs         Immutable log of admin/user/system actions
"""

from .user import UserORM
from .user_preference import UserPreferenceORM
from .role import RoleORM
from .package import PackageORM
from .server import ServerORM
from .vpn_key import VPNKeyORM
from .order import OrderORM
from .wallet import WalletORM
from .transaction import TransactionORM
from .referral import ReferralORM
from .free_trial import FreeTrialORM
from .setting import SettingORM
from .notification import NotificationORM
from .audit_log import AuditLogORM
from .payment_submission import PaymentSubmissionORM
from .server_reservation import ServerCapacityReservationORM
from .vpn_provisioning_operation import VPNProvisioningOperationORM
from .free_trial_claim import FreeTrialClaimORM
from .free_trial_entitlement import FreeTrialEntitlementORM
from .free_trial_entitlement_redemption import FreeTrialEntitlementRedemptionORM
from .free_trial_upgrade import FreeTrialUpgradeOfferORM, FreeTrialUpgradeORM, FreeTrialRestrictionORM
from .free_trial_rate_limit import FreeTrialRateLimitORM
from .referral_token import ReferralTokenORM
from .referral_reward import ReferralRewardORM, ReferralRiskEventORM
from .referral_risk_observation import ReferralRiskObservationORM
from .background_job import BackgroundJobORM, BackgroundJobStatus
from .backup_record import BackupRecordORM, BackupStatus, BackupType, RestoreTestStatus
from .maintenance import AlertSeverity, AlertStatus, AutoEndPolicy, CustomerImpact, IncidentSeverity, IncidentStatus, MaintenanceActionORM, MaintenanceReason, MaintenanceScope, MaintenanceState, MaintenanceWindowORM, MaintenanceWindowStatus, OperationalAlertORM, OperationalIncidentORM
from .mission import MissionORM, UserMissionProgressORM, MissionProgressEventORM
from .promo import PromoCodeORM, PromoRedemptionORM

__all__ = [
    "UserORM",
    "UserPreferenceORM",
    "RoleORM",
    "PackageORM",
    "ServerORM",
    "VPNKeyORM",
    "OrderORM",
    "WalletORM",
    "TransactionORM",
    "ReferralORM",
    "FreeTrialORM",
    "SettingORM",
    "NotificationORM",
    "AuditLogORM",
    "PaymentSubmissionORM",
    "ServerCapacityReservationORM",
    "VPNProvisioningOperationORM",
    "FreeTrialClaimORM",
    "FreeTrialEntitlementORM",
    "FreeTrialEntitlementRedemptionORM",
    "FreeTrialUpgradeOfferORM",
    "FreeTrialUpgradeORM",
    "FreeTrialRestrictionORM",
    "FreeTrialRateLimitORM",
    "ReferralTokenORM",
    "ReferralRewardORM",
    "ReferralRiskEventORM",
    "ReferralRiskObservationORM",
    "BackgroundJobORM",
    "BackgroundJobStatus",
    "BackupRecordORM",
    "BackupStatus",
    "BackupType",
    "RestoreTestStatus",
    "MaintenanceActionORM",
    "MaintenanceWindowORM",
    "MaintenanceWindowStatus",
    "MaintenanceState",
    "MaintenanceScope",
    "MaintenanceReason",
    "AutoEndPolicy",
    "OperationalAlertORM",
    "AlertStatus",
    "AlertSeverity",
    "OperationalIncidentORM",
    "IncidentStatus",
    "IncidentSeverity",
    "CustomerImpact",
    "MissionORM",
    "UserMissionProgressORM",
    "MissionProgressEventORM",
    "PromoCodeORM",
    "PromoRedemptionORM",
]
