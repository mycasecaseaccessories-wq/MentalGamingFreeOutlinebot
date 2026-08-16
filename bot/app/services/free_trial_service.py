from datetime import datetime,timezone
from sqlalchemy import select
from app.core.result import Failure,Success
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.package import PackageORM
class FreeTrialService:
 def __init__(self,db):self.db=db
 async def claim(self,*,user_id,package_id,idempotency_key):
  if user_id<=0 or package_id<=0 or not idempotency_key:return Failure('invalid_claim','Free Trial claim identity is invalid.')
  async with self.db.session() as s:
   e=(await s.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.user_id==user_id))).scalar_one_or_none()
   if e is not None:return Success(e) if e.idempotency_key==idempotency_key else Failure('trial_already_claimed','Free Trial has already been claimed.')
   p=(await s.execute(select(PackageORM).where(PackageORM.id==package_id,PackageORM.package_type=='free_trial',PackageORM.is_active.is_(True),PackageORM.visible.is_(True),PackageORM.status=='active'))).scalar_one_or_none()
   if p is None:return Failure('trial_unavailable','Free Trial is not currently available.')
   c=FreeTrialClaimORM(user_id=user_id,package_id=package_id,idempotency_key=idempotency_key,status='claimed',claimed_at=datetime.now(timezone.utc));s.add(c);await s.commit();return Success(c)
