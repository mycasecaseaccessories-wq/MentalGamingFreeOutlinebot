from sqlalchemy import select
from database.models.vpn_provisioning_operation import VPNProvisioningOperationORM
from .base import BaseRepository
class VPNProvisioningOperationRepository(BaseRepository[VPNProvisioningOperationORM, VPNProvisioningOperationORM]):
    orm_class=VPNProvisioningOperationORM
    domain_class=VPNProvisioningOperationORM
    async def get_by_idempotency(self,key,*,for_update=False):
        q=select(VPNProvisioningOperationORM).where(VPNProvisioningOperationORM.idempotency_key==key)
        if for_update: q=q.with_for_update()
        return (await self._session.execute(q)).scalar_one_or_none()
    async def get_by_public_id(self,public_id):
        return (await self._session.execute(select(VPNProvisioningOperationORM).where(VPNProvisioningOperationORM.public_operation_id==public_id))).scalar_one_or_none()
    async def get_by_provider_key(self,server_id,provider_key_id):
        return (await self._session.execute(select(VPNProvisioningOperationORM).where(VPNProvisioningOperationORM.server_id==server_id,VPNProvisioningOperationORM.provider_key_id==provider_key_id))).scalars().first()
