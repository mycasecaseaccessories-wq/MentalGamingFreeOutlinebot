from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import PermissionDeniedException
from app.core.result import Failure, Success
from app.services.admin_authorization_service import AdminAuthorizationService
from app.events import EventType, bus
from app.integrations.outline_provider import OutlineProvider, OutlineProviderError, OutlineProviderTimeout
from app.models.server_selection import ServerSelectionRequest
from app.models.vpn_provisioning import ProvisioningSource, VPNProvisioningRequest, VPNProvisioningSuccess
from app.security.credential_vault import CredentialVault
from database.models.order import OrderORM
from database.models.package import PackageORM
from database.models.server import ServerORM
from database.models.user import UserORM
from database.models.vpn_key import VPNKeyORM
from database.models.vpn_provisioning_operation import VPNProvisioningOperationORM
from database.repositories.server_repository import ServerRepository
from database.repositories.vpn_key_repository import VPNKeyRepository
from database.repositories.vpn_provisioning_operation_repository import VPNProvisioningOperationRepository
from .base import BaseService

_IN_FLIGHT = {"selecting_server", "reserved", "creating_remote_key", "remote_key_created", "persisting_local_key"}
_TERMINAL = {"completed", "failed", "cancelled", "compensation_required", "unknown"}


class VPNProvisioningService(BaseService):
    """Phase 4.1 provisioning saga; remote mutation and local persistence are explicit."""

    def __init__(
        self,
        db,
        *,
        selection_service,
        reservation_service,
        provider_registry=None,
        provider=None,
        vault=None,
        authorization_service: AdminAuthorizationService | None = None,
    ):
        super().__init__(db)
        self.selection_service = selection_service
        self.reservation_service = reservation_service
        self.provider_registry = provider_registry
        self.provider = provider or OutlineProvider()
        self.vault = vault or CredentialVault()
        self.authorization = authorization_service

    async def provision(self, request: VPNProvisioningRequest, *, actor_user_id: int | None = None):
        try:
            request.validate()
        except ValueError as exc:
            return Failure("validation_error", str(exc))
        if not await self._authorized(actor_user_id or request.user_id, request.user_id):
            return Failure("permission_denied", "Provisioning permission denied.")
        operation = await self._get_operation(request)
        if operation is None:
            return Failure("idempotency_in_progress", "Provisioning operation is already in progress.")
        if operation.status == "completed" and operation.local_vpn_key_id:
            return await self._existing(operation)
        if operation.status in _IN_FLIGHT:
            code = "provisioning_unknown" if operation.status in {"remote_key_created", "persisting_local_key"} else "idempotency_in_progress"
            return Failure(code, "Provisioning operation is already in progress; do not retry blindly.", details={"operation_id": operation.public_operation_id})
        if operation.status in _TERMINAL:
            return Failure(operation.error_code or "conflict", operation.error_message or "Provisioning operation is terminal.", details={"operation_id": operation.public_operation_id})

        order = package = None
        if request.source_type == ProvisioningSource.PAID_ORDER:
            order, package, error = await self._paid_order(request)
            if error:
                await self._fail(operation.public_operation_id, *error)
                return Failure(*error)
        elif request.package_id:
            async with self.db.session() as session:
                package = await session.get(PackageORM, request.package_id)

        selection = await self.selection_service.select(
            ServerSelectionRequest(
                workload_type=request.workload_type,
                plan=getattr(package, "package_type", None),
                package_id=request.package_id or getattr(package, "id", None),
                preferred_country=request.preferred_country or getattr(package, "country", None),
                required_country=getattr(package, "country", None) if getattr(package, "server_policy", "auto") == "country" else None,
                provider_type=request.provider_type,
                preferred_server_id=request.specific_server_id,
                required_server_id=request.specific_server_id,
                allow_fallback=request.allow_fallback,
                reservation_required=request.reserve_capacity,
                request_reference=operation.public_operation_id,
            )
        )
        if selection.selected is None:
            reason = selection.no_server_reason or "no_eligible_server"
            await self._fail(operation.public_operation_id, "no_eligible_server", reason)
            return Failure("no_eligible_server", reason)

        selected_id = selection.selected.server_id
        await self._set(operation.public_operation_id, "selecting_server", server_public_id=selected_id)
        await bus.emit(EventType.VPN_SERVER_SELECTED, operation_id=operation.public_operation_id, server_public_id=selected_id)
        reservation_token = None
        if request.reserve_capacity:
            reserved = await self.reservation_service.reserve(selected_id, request.workload_type, operation.public_operation_id)
            if reserved.is_failure:
                await self._fail(operation.public_operation_id, "reservation_failed", reserved.error.message)
                return reserved
            reservation_token = reserved.value.public_reservation_id
            await self._set(operation.public_operation_id, "reserved", reservation_token=reservation_token)

        server = await self._revalidate(selected_id)
        if server is None:
            if reservation_token:
                await self.reservation_service.release_reservation(reservation_token)
            await self._fail(operation.public_operation_id, "server_unavailable", "Selected server is no longer eligible.")
            return Failure("server_unavailable", "Selected server is no longer eligible.")
        provider = self._provider(request.provider_type)
        management_url = self._management_url(server)
        if not management_url:
            if reservation_token:
                await self.reservation_service.release_reservation(reservation_token)
            await self._fail(operation.public_operation_id, "provider_unavailable", "Provider credentials are unavailable.")
            return Failure("provider_unavailable", "Provider credentials are unavailable.")

        await self._set(operation.public_operation_id, "creating_remote_key")
        try:
            remote = await provider.create_key(management_url=management_url, name=provider.safe_key_name(public_order_id=getattr(order, "public_order_id", None), operation_id=operation.public_operation_id))
        except OutlineProviderTimeout as exc:
            if reservation_token:
                await self.reservation_service.release_reservation(reservation_token)
            await self._set(operation.public_operation_id, "unknown", error_code="provisioning_unknown", error_message=str(exc))
            return Failure("provisioning_unknown", str(exc), details={"operation_id": operation.public_operation_id})
        except OutlineProviderError as exc:
            if reservation_token:
                await self.reservation_service.release_reservation(reservation_token)
            await self._fail(operation.public_operation_id, "remote_key_creation_failed", str(exc))
            return Failure("remote_key_creation_failed", str(exc))

        await self._set(operation.public_operation_id, "remote_key_created", provider_key_id=remote.provider_key_id)
        await bus.emit(EventType.VPN_REMOTE_KEY_CREATED, operation_id=operation.public_operation_id, provider_key_id=remote.provider_key_id)
        try:
            local_id = await self._persist(request, order, package, server, operation.public_operation_id, remote)
        except Exception:
            try:
                await provider.delete_key(management_url=management_url, provider_key_id=remote.provider_key_id)
            except Exception:
                await self._set(operation.public_operation_id, "compensation_required", provider_key_id=remote.provider_key_id, error_code="compensation_failed", error_message="Remote compensation failed; administrator reconciliation required.")
                if reservation_token:
                    await self.reservation_service.release_reservation(reservation_token)
                await bus.emit(EventType.VPN_COMPENSATION_REQUIRED, operation_id=operation.public_operation_id, provider_key_id=remote.provider_key_id)
                return Failure("compensation_failed", "VPN key requires administrator reconciliation.")
            if reservation_token:
                await self.reservation_service.release_reservation(reservation_token)
            await self._fail(operation.public_operation_id, "persistence_failed", "VPN key could not be saved locally.")
            return Failure("persistence_failed", "VPN key could not be saved locally.")

        await self._set(operation.public_operation_id, "completed", local_vpn_key_id=local_id, provider_key_id=remote.provider_key_id, completed_at=datetime.now(timezone.utc))
        if reservation_token:
            await self.reservation_service.commit_reservation(reservation_token)
        await bus.emit(EventType.VPN_KEY_PERSISTED, operation_id=operation.public_operation_id, vpn_key_id=local_id)
        await bus.emit(EventType.VPN_PROVISIONED, operation_id=operation.public_operation_id, vpn_key_id=local_id, server_public_id=server.public_server_id)
        return Success(VPNProvisioningSuccess(operation.public_operation_id, local_id, server.public_server_id, remote.provider_type, remote.provider_key_id, remote.access_url, selection.selected.fallback_used))

    async def _authorized(self, actor_id: int, target_id: int) -> bool:
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_id)
            if actor is None or not actor.is_active or actor.status in {"banned", "suspended", "inactive"}:
                return False
            if actor.id == target_id:
                return True
        if self.authorization is None:
            return False
        try:
            await self.authorization.require_permission_for_user(actor_id, "manage_users")
        except PermissionDeniedException:
            return False
        return True

    async def _get_operation(self, request):
        async with self.db.session() as session:
            repo = VPNProvisioningOperationRepository(session)
            existing = await repo.get_by_idempotency(request.idempotency_key, for_update=True)
            if existing:
                return existing
            row = VPNProvisioningOperationORM(public_operation_id="VP-" + secrets.token_urlsafe(10), idempotency_key=request.idempotency_key, request_reference=request.request_reference, user_id=request.user_id, order_id=request.order_id, package_id=request.package_id, provider_type=request.provider_type, status="pending", metadata_json={"source_type": request.source_type.value})
            session.add(row)
            try:
                await session.flush()
            except IntegrityError:
                return None
            return row

    async def _paid_order(self, request):
        async with self.db.session() as session:
            order = await session.get(OrderORM, request.order_id) if request.order_id else None
            if not order or order.user_id != request.user_id:
                return None, None, ("not_found", "Paid order was not found.")
            if order.status != OrderORM.STATUS_PAID or order.payment_status != OrderORM.PAYMENT_PAID:
                return None, None, ("order_not_paid", "Only a paid order can be provisioned.")
            if order.vpn_key_id:
                return None, None, ("order_already_provisioned", "This order already has a VPN key.")
            package = await session.get(PackageORM, order.package_id)
            return (order, package, None) if package else (None, None, ("not_found", "Package was not found."))

    async def _revalidate(self, public_id):
        async with self.db.session() as session:
            server = await ServerRepository(session).get_by_public_id(public_id)
            if server is None or server.archived_at is not None or not server.enabled or not server.is_active or server.maintenance_mode or server.health_status not in {ServerORM.HEALTH_OK, "healthy"}:
                return None
            return server

    def _provider(self, provider_type):
        return (self.provider_registry.get_or_none("vpn", provider_type) if self.provider_registry else None) or self.provider

    def _management_url(self, server):
        try:
            return self.vault.decrypt(server.credential_ciphertext) if server.credential_ciphertext else None
        except Exception:
            return None

    async def _persist(self, request, order, package, server, operation_id, remote):
        async with self.db.session() as session:
            operation = await VPNProvisioningOperationRepository(session).get_by_public_id(operation_id)
            existing = await VPNKeyRepository(session).get_by_outline_key_id(server.id, remote.provider_key_id)
            if existing:
                raise RuntimeError("provider key is already bound")
            package_limit = None if package is None or getattr(package, "data_limit_gb", None) is None else int(float(package.data_limit_gb) * (1024 ** 3))
            data_limit = request.requested_data_limit_bytes if request.requested_data_limit_bytes is not None else package_limit
            device_limit = request.requested_device_limit if request.requested_device_limit is not None else getattr(package, "max_devices", None)
            row = VPNKeyORM(user_id=request.user_id, server_id=server.id, outline_key_id=remote.provider_key_id, provider_type=remote.provider_type, order_id=request.order_id, provisioning_operation_id=operation.id, source_type=request.source_type.value, provisioned_at=datetime.now(timezone.utc), access_url=remote.access_url, name=remote.safe_metadata.get("name"), data_limit_bytes=data_limit, device_limit=device_limit, package_id=request.package_id or getattr(package, "id", None), key_type=request.workload_type, status="active", is_active=True)
            session.add(row)
            await session.flush()
            if order:
                locked = await session.get(OrderORM, order.id)
                if locked and locked.vpn_key_id is None:
                    locked.vpn_key_id = row.id
                    locked.status = OrderORM.STATUS_COMPLETED
                    locked.completed_at = datetime.now(timezone.utc)
            return row.id

    async def _set(self, public_id, status, **fields):
        async with self.db.session() as session:
            row = await VPNProvisioningOperationRepository(session).get_by_public_id(public_id)
            if row:
                row.status = status
                for name, value in fields.items():
                    if hasattr(row, name):
                        setattr(row, name, value)

    async def _fail(self, public_id, code, message):
        await self._set(public_id, "failed", error_code=code, error_message=message, completed_at=datetime.now(timezone.utc))
        await bus.emit(EventType.VPN_PROVISIONING_FAILED, operation_id=public_id, code=code)

    async def _existing(self, operation):
        async with self.db.session() as session:
            row = await session.get(VPNKeyORM, operation.local_vpn_key_id)
            if row is None:
                return Failure("binding_missing", "Local VPN key binding is missing.")
            return Success(VPNProvisioningSuccess(operation.public_operation_id, row.id, str(row.server_id), row.provider_type, row.outline_key_id, row.access_url))
