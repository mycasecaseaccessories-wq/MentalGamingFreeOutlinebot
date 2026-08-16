from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.result import Failure, Success
from database.models.membership_verification import MembershipTargetORM, UserMembershipVerificationORM
from database.models.user import UserORM
class MembershipVerificationService:
    def __init__(self, db, provider=None): self.db=db; self.provider=provider
    async def set_target(self, *, actor_user_id, target_type, target_id, invite_url=None, enabled=True):
        target_id = (target_id or '').strip()
        if target_type not in {'channel','group'} or not target_id: return Failure('invalid_target','Membership target is invalid.')
        async with self.db.session() as s:
            actor=await s.get(UserORM,actor_user_id)
            if actor is None or actor.role!='admin' or not actor.is_active: return Failure('unauthorized','Admin permission required.')
            for row in (await s.execute(select(MembershipTargetORM).where(MembershipTargetORM.enabled.is_(True)))).scalars().all(): row.enabled=False
            t=(await s.execute(select(MembershipTargetORM).where(MembershipTargetORM.target_type==target_type,MembershipTargetORM.target_id==target_id))).scalar_one_or_none()
            if t is None: t=MembershipTargetORM(target_type=target_type,target_id=target_id,invite_url=invite_url,revision=1,enabled=enabled,updated_by=actor_user_id); s.add(t)
            else: t.revision=int(t.revision or 0)+1; t.invite_url=invite_url; t.enabled=enabled; t.updated_by=actor_user_id
            await s.commit(); return Success(t)
    async def is_verified_for_current_target(self, *, user_id):
        async with self.db.session() as s:
            t=(await s.execute(select(MembershipTargetORM).where(MembershipTargetORM.enabled.is_(True)).order_by(MembershipTargetORM.id.desc()).limit(1))).scalar_one_or_none()
            if t is None: return True
            p=(await s.execute(select(UserMembershipVerificationORM).where(UserMembershipVerificationORM.user_id==user_id,UserMembershipVerificationORM.target_id==t.id,UserMembershipVerificationORM.target_revision==t.revision))).scalar_one_or_none()
            return p is not None
    async def record_verified(self, *, user_id, target_id, target_revision):
        async with self.db.session() as s:
            p=(await s.execute(select(UserMembershipVerificationORM).where(UserMembershipVerificationORM.user_id==user_id,UserMembershipVerificationORM.target_id==target_id))).scalar_one_or_none()
            if p is None: p=UserMembershipVerificationORM(user_id=user_id,target_id=target_id,target_revision=target_revision,verified_at=datetime.now(timezone.utc)); s.add(p)
            else: p.target_revision=target_revision; p.verified_at=datetime.now(timezone.utc)
            await s.commit(); return Success(p)
