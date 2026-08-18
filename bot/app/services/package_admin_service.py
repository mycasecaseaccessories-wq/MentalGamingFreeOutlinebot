from decimal import Decimal
from sqlalchemy import select
from app.core.result import Failure,Success
from app.services.admin_authorization_service import AdminAuthorizationService
from database.models.package import PackageORM
from database.models.user import UserORM
class PackageAdminService:
 def __init__(self,db):self.db=db
 async def update_free_trial(self,*,actor_user_id,package_id,amount,currency,duration_days,data_limit_gb,max_devices,visible,enabled):
  if amount<0 or duration_days<=0 or (data_limit_gb is not None and data_limit_gb<=0) or (max_devices is not None and max_devices<=0):return Failure('invalid_package_policy','Free Trial policy values are invalid.')
  async with self.db.session() as s:
   actor=await s.get(UserORM,actor_user_id)
   if actor is None or not await AdminAuthorizationService(self.db).has_permission_for_user(actor.id, "manage_promos"):return Failure('unauthorized','Admin permission required.')
   p=await s.get(PackageORM,package_id,with_for_update=True)
   if p is None or p.package_type!='free_trial':return Failure('not_found','Free Trial package not found.')
   p.price=amount;p.currency=currency.upper();p.duration_days=duration_days;p.data_limit_gb=data_limit_gb;p.max_devices=max_devices;p.visible=bool(visible);p.is_active=bool(enabled);p.status='active' if enabled else 'disabled';await s.commit();return Success(p.id)
 async def get_active_free_trial(self):
  async with self.db.session() as s:
   r=await s.execute(select(PackageORM).where(PackageORM.package_type=='free_trial',PackageORM.is_active.is_(True),PackageORM.visible.is_(True),PackageORM.status=='active').order_by(PackageORM.sort_order.asc(),PackageORM.id.asc()).limit(1));return r.scalar_one_or_none()
