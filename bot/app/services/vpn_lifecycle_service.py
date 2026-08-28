from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import select
from app.core.result import Failure,Success
from app.services.admin_authorization_service import AdminAuthorizationService
from app.events import EventType,bus
from app.integrations.outline_provider import OutlineProvider,OutlineProviderError,OutlineProviderTimeout
from app.models.enums import VPNKeyStatus
from app.models.vpn_lifecycle import LifecycleReason,ProviderCleanupStatus,VPNKeyStateMachine,VPNLifecyclePolicy,VPNLifecycleSummary
from app.security.credential_vault import CredentialVault
from database.models.order import OrderORM
from database.models.server import ServerORM
from database.models.user import UserORM
from database.models.vpn_key import VPNKeyORM
from .base import BaseService
from .maintenance_service import MaintenanceService, MaintenanceBlockedError
class VPNLifecycleService(BaseService):
 def __init__(self,db,*,provider=None,vault=None,policy=None,maintenance_service: MaintenanceService | None = None): super().__init__(db); self.provider=provider or OutlineProvider(); self.vault=vault or CredentialVault(); self.policy=policy or VPNLifecyclePolicy(); self.maintenance_service=maintenance_service
 async def activate_key(self,*,key_id,actor_user_id,duration_days=None):
  if self.maintenance_service is not None:
   try: await self.maintenance_service.assert_operation_allowed("vpn_lifecycle", "UPDATE")
   except MaintenanceBlockedError: return Failure('maintenance_active','VPN lifecycle changes are temporarily unavailable during maintenance.')
  async with self.db.session() as s:
   k=(await s.execute(select(VPNKeyORM).where(VPNKeyORM.id==key_id).with_for_update())).scalar_one_or_none()
   if k is None:return Failure('not_found','VPN key was not found.')
   if not await self._auth(s,k,actor_user_id):return Failure('permission_denied','VPN lifecycle permission denied.')
   if k.status in {VPNKeyStatus.EXPIRED.value,VPNKeyStatus.REVOKED.value}:return Failure('invalid_transition','Key cannot be activated without renewal.')
   if k.status==VPNKeyStatus.ACTIVE.value and k.activated_at:return Success(self.summary(k))
   days,err=await self._duration(s,k,duration_days)
   if err:return Failure(*err)
   now=datetime.now(timezone.utc); VPNKeyStateMachine.validate_transition(k.status,VPNKeyStatus.ACTIVE.value); k.activated_at=now; k.expires_at=self.policy.calculate_expires_at(now,days); k.status=VPNKeyStatus.ACTIVE.value; k.is_active=True; await s.flush(); result=self.summary(k)
  await bus.emit(EventType.VPN_KEY_ACTIVATED,key_id=key_id,expires_at=result.expires_at); return Success(result)
 async def extend_key_to(self, *, key_id, actor_user_id, target_expires_at):
  """Converge an active key to an absolute expiry target without double-extension."""
  if self.maintenance_service is not None:
   try: await self.maintenance_service.assert_operation_allowed("vpn_lifecycle", "UPDATE")
   except MaintenanceBlockedError: return Failure('maintenance_active','VPN lifecycle changes are temporarily unavailable during maintenance.')
  async with self.db.session() as s:
   k=(await s.execute(select(VPNKeyORM).where(VPNKeyORM.id==key_id).with_for_update())).scalar_one_or_none()
   if k is None:return Failure('not_found','VPN key was not found.')
   if not await self._auth(s,k,actor_user_id):return Failure('permission_denied','VPN lifecycle permission denied.')
   if k.activated_at is None:return Failure('invalid_transition','VPN key is not active.')
   target = target_expires_at if target_expires_at.tzinfo else target_expires_at.replace(tzinfo=timezone.utc)
   if k.expires_at is not None and k.expires_at >= target:return Success(self.summary(k))
   k.expires_at=target
   if k.status != VPNKeyStatus.ACTIVE.value:
    k.status=VPNKeyStatus.ACTIVE.value; k.is_active=True
   await s.flush(); result=self.summary(k)
  await bus.emit(EventType.VPN_KEY_ACTIVATED,key_id=key_id,expires_at=result.expires_at)
  return Success(result)

 async def expire_due_key(self,*,key_id,actor_user_id=0):
  async with self.db.session() as s:
   k=(await s.execute(select(VPNKeyORM).where(VPNKeyORM.id==key_id).with_for_update())).scalar_one_or_none()
   if k is None:return Failure('not_found','VPN key was not found.')
   if k.status==VPNKeyStatus.REVOKED.value:return Success(self.summary(k))
   if not self.policy.is_expired(k.expires_at):return Failure('not_due','VPN key has not expired.')
   if k.status==VPNKeyStatus.EXPIRED.value and k.lifecycle_cleanup_status==ProviderCleanupStatus.COMPLETED.value:return Success(self.summary(k))
   VPNKeyStateMachine.validate_transition(k.status,VPNKeyStatus.EXPIRED.value); k.status=VPNKeyStatus.EXPIRED.value; k.is_active=False; k.lifecycle_reason=LifecycleReason.EXPIRY.value; k.lifecycle_cleanup_status=ProviderCleanupStatus.PENDING.value; await s.flush(); server=await s.get(ServerORM,k.server_id)
   if server is None or not server.credential_ciphertext:k.lifecycle_cleanup_status=ProviderCleanupStatus.FAILED.value; await s.flush(); return Failure('provider_unavailable','Provider cleanup unavailable.')
   try:
    management_url=self.vault.decrypt(server.credential_ciphertext)
    if isinstance(self.provider, OutlineProvider):
     await self.provider.delete_key(management_url=management_url,provider_key_id=k.outline_key_id,expected_cert_sha256=server.cert_sha256)
    else:
     await self.provider.revoke_key(management_url=management_url,provider_key_id=k.outline_key_id)
   except (OutlineProviderTimeout,OutlineProviderError) as e:k.lifecycle_cleanup_status=ProviderCleanupStatus.FAILED.value; k.lifecycle_cleanup_attempts=int(k.lifecycle_cleanup_attempts or 0)+1; k.lifecycle_cleanup_error=str(e)[:128]; await s.flush(); return Failure('cleanup_failed','Provider cleanup failed.')
   k.lifecycle_cleanup_status=ProviderCleanupStatus.COMPLETED.value; k.lifecycle_cleanup_at=datetime.now(timezone.utc); k.lifecycle_cleanup_error=None; await s.flush(); result=self.summary(k)
  await bus.emit(EventType.VPN_KEY_EXPIRED,key_id=key_id); return Success(result)
 async def suspend_key(self,*,key_id,actor_user_id,reason='admin'): return Failure('unsupported','Provider does not support reversible suspension.')
 async def resume_key(self,*,key_id,actor_user_id): return Failure('unsupported','Provider does not support reversible resumption.')
 async def revoke_key(self,*,key_id,actor_user_id,reason='admin'): return await self.expire_due_key(key_id=key_id,actor_user_id=actor_user_id)
 async def _duration(self,s,k,requested):
  if k.order_id:
   o=await s.get(OrderORM,k.order_id); days=o.duration_days_snapshot if o else None
   if days is None:return None,('duration_not_configured','Order duration is missing.')
   if requested is not None and int(requested)!=int(days):return None,('duration_conflict','Duration conflicts with order snapshot.')
   return int(days),None
  if requested is None:return None,('duration_required','Duration is required.')
  try:return self.policy.validate_duration(int(requested)),None
  except ValueError as e:return None,('invalid_duration',str(e))
 async def _auth(self, s, k, uid):
  a=await s.get(UserORM,uid)
  if a is None or not a.is_active or a.status in {"banned", "suspended", "inactive"}:
   return False
  if a.id == k.user_id:
   return True
  return await AdminAuthorizationService(self.db).has_permission_for_user(a.id, "manage_users")
 def summary(self,k): return VPNLifecycleSummary(k.id,k.status,k.activated_at,k.expires_at,self.policy.remaining(k.expires_at),self.policy.is_expiring_soon(k.expires_at),k.lifecycle_cleanup_status)
