from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.base import BaseModel
class MembershipTargetORM(BaseModel):
    __tablename__='membership_targets'
    target_type: Mapped[str]=mapped_column(String(16),nullable=False)
    target_id: Mapped[str]=mapped_column(String(128),nullable=False)
    invite_url: Mapped[str|None]=mapped_column(Text,nullable=True)
    revision: Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    enabled: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    updated_by: Mapped[int|None]=mapped_column(Integer,nullable=True)
    __table_args__=(UniqueConstraint('target_type','target_id',name='uq_membership_target_identity'),)
class UserMembershipVerificationORM(BaseModel):
    __tablename__='user_membership_verifications'
    user_id: Mapped[int]=mapped_column(Integer,nullable=False,index=True)
    target_id: Mapped[int]=mapped_column(Integer,nullable=False,index=True)
    target_revision: Mapped[int]=mapped_column(Integer,nullable=False)
    verified_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    __table_args__=(UniqueConstraint('user_id','target_id',name='uq_user_membership_target'),)
