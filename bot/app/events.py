from __future__ import annotations
import asyncio
import logging
from enum import Enum, unique
from typing import Any, Callable, Coroutine
logger=logging.getLogger(__name__)
Handler=Callable[...,Coroutine[Any,Any,None]]
@unique
class EventType(str,Enum):
    APP_STARTED='app.started'; APP_STOPPED='app.stopped'; APP_ERROR='app.error'
    USER_REGISTERED='user.registered'; USER_CREATED='user.created'; USER_UPDATED='user.updated'; USER_RETURNED='user.returned'; USER_STARTED_BOT='user.started_bot'; USER_BANNED='user.banned'; USER_UNBANNED='user.unbanned'; USER_LANGUAGE_CHANGED='user.language_changed'
    SETTINGS_CHANGED='settings.changed'; FEATURE_FLAG_CHANGED='settings.feature_flag_changed'
    SERVER_ADDED='server.added'; SERVER_UPDATED='server.updated'; SERVER_REMOVED='server.removed'; SERVER_UNREACHABLE='server.unreachable'; SERVER_SYNC_COMPLETED='server.sync_completed'; SERVER_SYNC_FAILED='server.sync_failed'; SERVER_HEALTH_CHANGED='server.health_changed'
    SERVER_CAPACITY_RESERVED = "server.capacity_reserved"
    SERVER_CAPACITY_RESERVATION_COMMITTED = "server.capacity_reservation_committed"
    SERVER_CAPACITY_RESERVATION_RELEASED = "server.capacity_reservation_released"
    SERVER_CAPACITY_RESERVATION_EXPIRED = "server.capacity_reservation_expired"
    SERVER_SELECTION_REQUESTED = "server.selection_requested"
    SERVER_SELECTED = "server.selected"
    SERVER_SELECTION_FAILED = "server.selection_failed"
    SERVER_FALLBACK_USED = "server.fallback_used"
    PROVISION_STARTED='provision.started'; PROVISION_PREFLIGHT_COMPLETED='provision.preflight_completed'; PROVISION_INSTALLATION_STARTED='provision.installation_started'; PROVISION_INSTALLATION_COMPLETED='provision.installation_completed'; PROVISION_VERIFICATION_FAILED='provision.verification_failed'; PROVISION_COMPLETED='provision.completed'; PROVISION_FAILED='provision.failed'
    ORDER_CREATED='order.created'; ORDER_COMPLETED='order.completed'; ORDER_CANCELLED='order.cancelled'; PACKAGE_PURCHASED='package.purchased'
    FREE_TRIAL_UPGRADE_ORDER_CREATED='free_trial.upgrade_order_created'; FREE_TRIAL_UPGRADE_PAYMENT_CONFIRMED='free_trial.upgrade_payment_confirmed'; FREE_TRIAL_UPGRADE_FULFILLMENT_STARTED='free_trial.upgrade_fulfillment_started'; FREE_TRIAL_UPGRADE_FULFILLED='free_trial.upgrade_fulfilled'; FREE_TRIAL_UPGRADE_FULFILLMENT_FAILED='free_trial.upgrade_fulfillment_failed'; FREE_TRIAL_CONVERTED_TO_PAID='free_trial.converted_to_paid'; FREE_TRIAL_RISK_EVALUATED='free_trial.risk_evaluated'; FREE_TRIAL_RECOVERY_PERFORMED='free_trial.recovery_performed'; REFERRAL_SYSTEM_ENABLED='referral.system_enabled'; REFERRAL_SYSTEM_DISABLED='referral.system_disabled'; REFERRAL_LINK_VIEWED='referral.link_viewed'; REFERRAL_ATTRIBUTED='referral.attributed'; REFERRAL_REGISTRATION_COMPLETED='referral.registration_completed'; REFERRAL_INVALID='referral.invalid'; REFERRAL_INVALIDATED='referral.invalidated'; REFERRAL_QUALIFIED='referral.qualified'; REFERRAL_REVIEW_REQUIRED='referral.review_required'; REFERRAL_REWARD_ELIGIBLE='referral.reward_eligible'; REFERRAL_REWARD_CREATED='referral.reward_created'; REFERRAL_REWARD_GRANTED='referral.reward_granted'; REFERRAL_REWARD_FAILED='referral.reward_failed'; REFERRAL_REWARD_LIMIT_REACHED='referral.reward_limit_reached'; REFERRAL_REWARD_RETRY_SCHEDULED='referral.reward_retry_scheduled'
    KEY_ISSUED='key.issued'; KEY_REVOKED='key.revoked'; KEY_EXPIRED='key.expired'; VPN_GENERATED='vpn.generated'; VPN_AUTOMATION_READY='vpn.automation_ready'; WALLET_UPDATED='wallet.updated'; WALLET_DEBITED='wallet.debited'; WALLET_PAYMENT_COMPLETED='wallet.payment_completed'; ORDER_PAID='order.paid'; MANUAL_PAYMENT_SUBMITTED='manual_payment.submitted'; MANUAL_PAYMENT_APPROVED='manual_payment.approved'; MANUAL_PAYMENT_REJECTED='manual_payment.rejected'; PAYMENT_REVIEW_COMPLETED='payment_review.completed'; NOTIFICATION_SENT='notification.sent'
    FREE_TRIAL_ACTIVATED='free_trial.activated'
    MISSION_ACTIVATED='mission.activated'; MISSION_PROGRESS_UPDATED='mission.progress_updated'; MISSION_COMPLETED='mission.completed'; MISSION_REWARD_PENDING='mission.reward_pending'; MISSION_REWARD_GRANTED='mission.reward_granted'; MISSION_REWARD_FAILED='mission.reward_failed'; MISSION_EXPIRED='mission.expired'; MISSION_DAILY_CHECK_IN='mission.daily_check_in'
    PROMO_CREATED='promo.created'; PROMO_ACTIVATED='promo.activated'; PROMO_REDEMPTION_RESERVED='promo.redemption_reserved'; PROMO_REDEEMED='promo.redeemed'; PROMO_REDEMPTION_FAILED='promo.redemption_failed'; PROMO_EXPIRED='promo.expired'; PROMO_LIMIT_REACHED='promo.limit_reached'
    REFERRAL_RISK_SIGNAL_DETECTED='referral.risk_signal_detected'; REFERRAL_REVIEW_RESOLVED='referral.review_resolved'; REFERRAL_REWARD_HELD='referral.reward_held'; REFERRAL_REWARD_RELEASED='referral.reward_released'; REFERRAL_REWARD_BLOCKED='referral.reward_blocked'; REFERRAL_REWARD_UNBLOCKED='referral.reward_unblocked'; RISK_POLICY_CHANGED='risk.policy_changed'; GROWTH_RECONCILIATION_SCANNED='growth.reconciliation_scanned'; GROWTH_ENTITLEMENT_EXPIRED='growth.entitlement_expired'; BACKGROUND_JOB_ENQUEUED='background_job.enqueued'; BACKGROUND_JOB_COMPLETED='background_job.completed'; BACKGROUND_JOB_FAILED='background_job.failed'; BACKGROUND_JOB_DEAD_LETTERED='background_job.dead_lettered'; BACKGROUND_JOB_RECOVERED='background_job.recovered';     BACKUP_CREATED='backup.created'; BACKUP_VERIFIED='backup.verified'; BACKUP_FAILED='backup.failed'; BACKUP_RETENTION_APPLIED='backup.retention_applied'; BACKUP_RESTORE_TESTED='backup.restore_tested'; BACKUP_RESTORE_PREPARED='backup.restore_prepared'; MAINTENANCE_SCHEDULED='maintenance.scheduled'; MAINTENANCE_STARTED='maintenance.started'; MAINTENANCE_EXTENDED='maintenance.extended'; MAINTENANCE_ENDED='maintenance.ended'; MAINTENANCE_CANCELLED='maintenance.cancelled'; MAINTENANCE_RECOVERY_FAILED='maintenance.recovery_failed'; EMERGENCY_MODE_ENABLED='maintenance.emergency_enabled'; EMERGENCY_MODE_DISABLED='maintenance.emergency_disabled'; INCIDENT_CREATED='incident.created'; INCIDENT_UPDATED='incident.updated'; INCIDENT_RESOLVED='incident.resolved'

class EventBus:
    def __init__(self): self._subscribers={}
    def on(self,event_type,*,priority=0):
        def deco(handler): self.subscribe(event_type,handler,priority=priority); return handler
        return deco
    def subscribe(self,event_type,handler,*,priority=0): self._subscribers.setdefault(event_type,[]).append((priority,handler)); self._subscribers[event_type].sort(key=lambda x:x[0],reverse=True)
    def unsubscribe(self,event_type,handler):
        items=self._subscribers.get(event_type,[])
        for i,(_,candidate) in enumerate(items):
            if candidate is handler: items.pop(i); return True
        return False
    def subscriber_count(self,event_type): return len(self._subscribers.get(event_type,[]))
    def clear(self,event_type=None): self._subscribers.clear() if event_type is None else self._subscribers.pop(event_type,None)
    async def emit(self,event_type,**payload):
        async def call(handler):
            try: await handler(**payload)
            except Exception as exc: logger.error('Event handler failed for %s: %s',event_type,exc)
        await asyncio.gather(*(call(h) for _,h in list(self._subscribers.get(event_type,[]))))
class EventDispatcher:
    def __init__(self,bus=None): self.bus=bus or globals()['bus']
    async def publish(self,event_type,**payload): await self.bus.emit(event_type,**payload)
    async def dispatch(self,event_type,**payload): await self.bus.emit(event_type,**payload)
    async def broadcast(self,event_types,**payload):
        for event_type in event_types:
            await self.bus.emit(event_type, **payload)
bus=EventBus()
