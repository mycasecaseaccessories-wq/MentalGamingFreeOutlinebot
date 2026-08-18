from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import select
from app.core.result import Failure,Success
from app.services.admin_authorization_service import AdminAuthorizationService
from app.events import EventType,bus
from app.integrations.outline_provider import OutlineProvider,OutlineProviderError,OutlineProviderTimeout
from app.models.vpn_limits import VPNDataLimitPolicy,VPNLimitApplicationResult,VPNLimitStatus
from app.security.credential_vault import CredentialVault
from database.models.order import OrderORM
from database.models.server import ServerORM
from database.models.user import UserORM
from database.models.vpn_key import VPNKeyORM
from .base import BaseService
GB_BYTES=1024**3
class VPNDataLimitService(BaseService):
 def __init__(self,db,*,provider=None,vault=None,max_limit_bytes=None): super().__init__(db); self.provider=provider or OutlineProvider(); self.vault=vault or CredentialVault(); self.max_limit_bytes=max_limit_bytes
 async def apply_for_key(self,*,key_id,actor_user_id,requested_limit_bytes=None,operation_id):
  async with self.db.session() as s:
   k=(await s.execute(select(VPNKeyORM).where(VPNKeyORM.id==key_id).with_for_update())).scalar_one_or_none()
   if k is None:return Failure('not_found','VPN key was not found.')
   a=await s.get(UserORM,actor_user_id)
   if a is None or not a.is_active or a.status in {"banned", "suspended", "inactive"}:
    return Failure('permission_denied','Data-limit permission denied.')
   if a.id != k.user_id and not await AdminAuthorizationService(self.db).has_permission_for_user(a.id, "manage_users"):
    return Failure('permission_denied','Data-limit permission denied.')
   p,err=await self._policy(s,k,requested_limit_bytes)
   if err:return Failure(*err)
   try:p.validate(maximum_bytes=self.max_limit_bytes)
   except ValueError as e:return Failure('invalid_limit',str(e))
   if k.limit_status==VPNLimitStatus.APPLIED.value and k.data_limit_bytes==p.limit_bytes:return Success(self._result(k,operation_id,p.limit_bytes))
   k.limit_status=VPNLimitStatus.PENDING.value;k.limit_operation_id=operation_id;await s.flush();server=await s.get(ServerORM,k.server_id)
   if server is None or not getattr(k,'provider_type','outline')=='outline' or not server.credential_ciphertext:k.limit_status=VPNLimitStatus.UNSUPPORTED.value;await s.flush();return Failure('provider_unavailable','Data-limit provider unavailable.')
   try:
    url=self.vault.decrypt(server.credential_ciphertext);await self.provider.set_data_limit(management_url=url,provider_key_id=k.outline_key_id,limit_bytes=p.limit_bytes);remote=await self.provider.get_data_limit(management_url=url,provider_key_id=k.outline_key_id)
    if remote!=p.limit_bytes:k.limit_status=VPNLimitStatus.DRIFTED.value;k.remote_limit_bytes=remote;await s.flush();return Failure('limit_drifted','Remote data limit drifted.')
    usage=await self.provider.get_key_usage(management_url=url,provider_key_id=k.outline_key_id)
   except OutlineProviderTimeout as e:k.limit_status=VPNLimitStatus.FAILED.value;await s.flush();return Failure('limit_unknown',str(e))
   except OutlineProviderError as e:k.limit_status=VPNLimitStatus.FAILED.value;await s.flush();return Failure('limit_apply_failed',str(e))
   baseline=int(k.usage_baseline_bytes or 0) if k.limit_status==VPNLimitStatus.APPLIED.value else max(0,int(usage.used_bytes));k.data_limit_bytes=p.limit_bytes;k.remote_limit_bytes=remote;k.limit_source=p.source;k.limit_source_reference=p.source_reference;k.limit_applied_at=datetime.now(timezone.utc);k.provider_limit_verified=True;k.limit_status=VPNLimitStatus.APPLIED.value;k.usage_baseline_bytes=baseline;k.used_bytes=max(0,int(usage.used_bytes)-baseline);k.last_usage_sync_at=usage.measured_at;k.last_synced_at=usage.measured_at;await s.flush();result=self._result(k,operation_id,p.limit_bytes)
  await bus.emit(EventType.VPN_DATA_LIMIT_APPLIED,key_id=key_id,operation_id=operation_id,limit_bytes=result.limit_bytes,provider_verified=True);return Success(result)
 async def sync_key_usage(self,*,key_id):
  async with self.db.session() as s:
   k=(await s.execute(select(VPNKeyORM).where(VPNKeyORM.id==key_id).with_for_update())).scalar_one_or_none()
   if k is None:return Failure('not_found','VPN key was not found.')
   server=await s.get(ServerORM,k.server_id)
   if server is None or not server.credential_ciphertext:return Failure('provider_unavailable','Usage provider unavailable.')
   try:u=await self.provider.get_key_usage(management_url=self.vault.decrypt(server.credential_ciphertext),provider_key_id=k.outline_key_id)
   except (OutlineProviderTimeout,OutlineProviderError) as e:return Failure('usage_sync_failed',str(e))
   k.used_bytes=max(0,int(u.used_bytes)-int(k.usage_baseline_bytes or 0));k.last_usage_sync_at=u.measured_at;k.last_synced_at=u.measured_at;await s.flush();return Success({'key_id':k.id,'used_bytes':k.used_bytes,'remaining_bytes':self._remaining(k.data_limit_bytes,k.used_bytes),'last_synced_at':u.measured_at})
 async def reconcile_key(self,*,key_id): return Failure('not_implemented','Use provider reconciliation worker.')
 async def _policy(self,s,k,requested):
  if getattr(k,'order_id',None):
   o=await s.get(OrderORM,k.order_id);days=o.data_limit_gb_snapshot if o else None
   if days is None:return None,('limit_not_configured','Order data limit is missing.')
   limit=self._gb_to_bytes(days)
   if requested is not None and int(requested)!=limit:return None,('limit_conflict','Requested limit conflicts with order snapshot.')
   return VPNDataLimitPolicy(limit,'order_snapshot',str(o.public_order_id)),None
  if requested is None:return None,('limit_not_configured','Data limit is required.')
  return VPNDataLimitPolicy(int(requested),'authorized_request',str(k.id)),None
 @staticmethod
 def _gb_to_bytes(v):return int(Decimal(str(v))*Decimal(GB_BYTES))
 @staticmethod
 def _remaining(limit,used):return None if limit is None else max(int(limit)-max(int(used or 0),0),0)
 @staticmethod
 def _result(k,op,limit):
  used=max(int(k.used_bytes or 0),0);return VPNLimitApplicationResult(k.id,op,limit,VPNLimitStatus(k.limit_status),bool(k.provider_limit_verified),used,max(limit-used,0),k.last_usage_sync_at)
