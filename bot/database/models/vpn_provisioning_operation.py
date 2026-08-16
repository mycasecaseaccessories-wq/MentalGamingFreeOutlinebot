from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.base import BaseModel
class VPNProvisioningOperationORM(BaseModel):
 __tablename__='vpn_provisioning_operations'
 __table_args__=(UniqueConstraint('idempotency_key',name='uq_vpn_provisioning_idempotency'),UniqueConstraint('public_operation_id',name='uq_vpn_provisioning_public_id'))
 STATUS_PENDING='pending'; STATUS_SELECTING_SERVER='selecting_server'; STATUS_RESERVED='reserved'; STATUS_CREATING_REMOTE_KEY='creating_remote_key'; STATUS_REMOTE_KEY_CREATED='remote_key_created'; STATUS_PERSISTING_LOCAL_KEY='persisting_local_key'; STATUS_COMPLETED='completed'; STATUS_FAILED='failed'; STATUS_COMPENSATION_REQUIRED='compensation_required'; STATUS_CANCELLED='cancelled'; STATUS_UNKNOWN='unknown'
 public_operation_id:Mapped[str]=mapped_column(String(48),nullable=False,index=True)
 idempotency_key:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
 request_reference:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
 user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False,index=True)
 order_id:Mapped[int|None]=mapped_column(ForeignKey('orders.id',ondelete='RESTRICT'),nullable=True,index=True)
 package_id:Mapped[int|None]=mapped_column(ForeignKey('packages.id',ondelete='RESTRICT'),nullable=True,index=True)
 server_id:Mapped[int|None]=mapped_column(ForeignKey('servers.id',ondelete='RESTRICT'),nullable=True,index=True)
 provider_type:Mapped[str]=mapped_column(String(32),nullable=False,default='outline')
 provider_key_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
 local_vpn_key_id:Mapped[int|None]=mapped_column(ForeignKey('vpn_keys.id',ondelete='RESTRICT'),nullable=True,index=True)
 reservation_token:Mapped[str|None]=mapped_column(String(96),nullable=True,index=True)
 status:Mapped[str]=mapped_column(String(40),nullable=False,default='pending',index=True)
 error_code:Mapped[str|None]=mapped_column(String(64),nullable=True)
 error_message:Mapped[str|None]=mapped_column(Text,nullable=True)
 compensation_attempted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 compensation_failed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 metadata_json:Mapped[dict[str,Any]|None]=mapped_column('metadata',JSON,nullable=True)
