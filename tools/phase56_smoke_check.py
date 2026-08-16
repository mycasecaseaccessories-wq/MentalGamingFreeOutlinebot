from config.defaults import DEFAULT_SETTINGS, SettingKeys
from database.models.free_trial_upgrade import FreeTrialUpgradeOfferORM, FreeTrialUpgradeORM, FreeTrialRestrictionORM
from app.services.free_trial_upgrade_service import FreeTrialUpgradeService
from app.services.free_trial_abuse_service import FreeTrialAbuseProtectionService
from app.services.free_trial_analytics_service import FreeTrialAnalyticsService
from locales.en import TRANSLATIONS as EN
from locales.my import TRANSLATIONS as MY

required = [
    "free_trial.upgrade_successful",
    "free_trial.payment_received_processing",
    "free_trial.paid_conversion",
]
assert all(key in EN and key in MY for key in required)
assert any(item["key"] == SettingKeys.FREE_TRIAL_PAID_UPGRADE_ENABLED for item in DEFAULT_SETTINGS)
print("phase56 imports/defaults/locales: OK")
