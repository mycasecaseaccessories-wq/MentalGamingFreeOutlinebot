from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.result import Failure, Result, Success
from database.models.callback_security import CallbackActionORM, CallbackRateLimitORM

from .base import BaseService


@dataclass(frozen=True)
class CallbackReference:
    public_id: str
    token: str
    data: str


@dataclass(frozen=True)
class ConsumedCallback:
    public_id: str
    action_type: str
    actor_user_id: int
    resource_type: str | None
    resource_public_id: str | None
    state_version: str | None
    safe_metadata: dict[str, object]


class CallbackSecurityService(BaseService):
    """Durable security boundary for sensitive Telegram callback references."""

    PREFIX = "cb2"
    MAX_ACTION_TYPE = 96
    MAX_RESOURCE_TYPE = 64
    MAX_RESOURCE_ID = 128

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def parse_reference(cls, callback_data: str | None) -> tuple[str, str] | None:
        if not isinstance(callback_data, str):
            return None
        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        public_id, token = parts[1], parts[2]
        if not (8 <= len(public_id) <= 48 and 20 <= len(token) <= 64):
            return None
        if not all(ch.isalnum() or ch in "_-" for ch in public_id + token):
            return None
        return public_id, token

    async def issue(
        self,
        *,
        action_type: str,
        actor_user_id: int,
        actor_telegram_id: int,
        ttl_seconds: int = 300,
        chat_id: int | None = None,
        chat_type: str | None = None,
        resource_type: str | None = None,
        resource_public_id: str | None = None,
        state_version: str | None = None,
        safe_metadata: dict[str, object] | None = None,
        request_id: str | None = None,
    ) -> Result[CallbackReference]:
        action_type = str(action_type or "").strip()
        if not action_type or len(action_type) > self.MAX_ACTION_TYPE:
            return Failure("invalid_callback_action", "Callback action is invalid.")
        if resource_type is not None and len(str(resource_type)) > self.MAX_RESOURCE_TYPE:
            return Failure("invalid_callback_resource", "Callback resource is invalid.")
        if resource_public_id is not None and len(str(resource_public_id)) > self.MAX_RESOURCE_ID:
            return Failure("invalid_callback_resource", "Callback resource is invalid.")
        ttl_seconds = max(15, min(int(ttl_seconds), 3600))
        public_id = "cba_" + secrets.token_urlsafe(18).replace("/", "-").replace("+", "_")
        token = secrets.token_urlsafe(24).replace("/", "-").replace("+", "_")
        row = CallbackActionORM(
            public_id=public_id,
            token_digest=self._digest(token),
            action_type=action_type,
            actor_user_id=int(actor_user_id),
            actor_telegram_id=int(actor_telegram_id),
            chat_id=chat_id,
            chat_type=chat_type,
            resource_type=resource_type,
            resource_public_id=resource_public_id,
            state_version=state_version,
            expires_at=self._now() + timedelta(seconds=ttl_seconds),
            request_id=request_id,
            safe_metadata_json=json.dumps(
                safe_metadata or {}, sort_keys=True, separators=(",", ":")
            ),
        )
        async with self.db.session() as session:
            session.add(row)
            await session.flush()
        return Success(
            CallbackReference(
                public_id=public_id, token=token, data=f"{self.PREFIX}:{public_id}:{token}"
            )
        )

    async def action_type_for(self, callback_data: str | None) -> str | None:
        parsed = self.parse_reference(callback_data)
        if parsed is None:
            return None
        public_id, token = parsed
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(CallbackActionORM).where(CallbackActionORM.public_id == public_id)
                )
            ).scalar_one_or_none()
            if row is None or not secrets.compare_digest(row.token_digest, self._digest(token)):
                return None
            return row.action_type

    async def consume(  # noqa: PLR0911
        self,
        *,
        callback_data: str | None,
        action_type: str,
        actor_user_id: int,
        actor_telegram_id: int,
        chat_id: int | None = None,
        chat_type: str | None = None,
        expected_resource_type: str | None = None,
        expected_resource_public_id: str | None = None,
        expected_state_version: str | None = None,
        request_id: str | None = None,
    ) -> Result[ConsumedCallback]:
        parsed = self.parse_reference(callback_data)
        if parsed is None:
            return Failure("invalid_callback", "This callback is invalid.")
        public_id, token = parsed
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(CallbackActionORM)
                    .where(CallbackActionORM.public_id == public_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or not secrets.compare_digest(row.token_digest, self._digest(token)):
                return Failure("invalid_callback", "This callback is invalid.")
            if row.action_type != action_type:
                return Failure(
                    "callback_action_mismatch", "This callback is not valid for this action."
                )
            if row.actor_user_id != int(actor_user_id) or row.actor_telegram_id != int(
                actor_telegram_id
            ):
                return Failure("callback_not_owned", "This action belongs to another user.")
            if row.chat_id is not None and row.chat_id != chat_id:
                return Failure("callback_chat_mismatch", "This action is not valid in this chat.")
            if row.chat_type is not None and row.chat_type != chat_type:
                return Failure("callback_chat_mismatch", "This action is not valid in this chat.")
            if expected_resource_type is not None and row.resource_type != expected_resource_type:
                return Failure("callback_resource_mismatch", "This callback resource is invalid.")
            if (
                expected_resource_public_id is not None
                and row.resource_public_id != expected_resource_public_id
            ):
                return Failure("callback_resource_mismatch", "This callback resource is invalid.")
            if expected_state_version is not None and row.state_version != expected_state_version:
                return Failure("callback_stale", "This action is no longer current.")
            expires_at = (
                row.expires_at.replace(tzinfo=UTC)
                if row.expires_at.tzinfo is None
                else row.expires_at
            )
            if expires_at <= self._now():
                row.invalidated_at = self._now()
                row.invalidation_reason = "expired"
                return Failure("callback_expired", "This action has expired.")
            if row.invalidated_at is not None:
                return Failure("callback_invalidated", "This action is no longer available.")
            if row.consumed_at is not None:
                return Failure("callback_replayed", "This action was already used.")
            row.consumed_at = self._now()
            row.request_id = request_id or row.request_id
            await session.flush()
            result = ConsumedCallback(
                public_id=row.public_id,
                action_type=row.action_type,
                actor_user_id=row.actor_user_id,
                resource_type=row.resource_type,
                resource_public_id=row.resource_public_id,
                state_version=row.state_version,
                safe_metadata=json.loads(row.safe_metadata_json or "{}"),
            )
        return Success(result)

    async def check_rate_limit(
        self,
        *,
        actor_user_id: int,
        action_type: str,
        chat_id: int | None = None,
        limit: int = 20,
        window_seconds: int = 60,
    ) -> Result[bool]:
        limit = max(1, min(int(limit), 1000))
        window_seconds = max(1, min(int(window_seconds), 86400))
        scope_key = f"callback:{int(actor_user_id)}:{int(chat_id or 0)}:{str(action_type)[:96]}"
        now = self._now()
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(CallbackRateLimitORM)
                    .where(CallbackRateLimitORM.scope_key == scope_key)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                row = CallbackRateLimitORM(scope_key=scope_key, window_started_at=now, count=1)
                session.add(row)
                await session.flush()
                return Success(True)
            started = (
                row.window_started_at.replace(tzinfo=UTC)
                if row.window_started_at.tzinfo is None
                else row.window_started_at
            )
            if now - started >= timedelta(seconds=window_seconds):
                row.window_started_at = now
                row.count = 1
                await session.flush()
                return Success(True)
            if int(row.count or 0) >= limit:
                return Success(False)
            row.count = int(row.count or 0) + 1
            await session.flush()
            return Success(True)

    async def invalidate(self, public_id: str, *, reason: str = "invalidated") -> bool:
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(CallbackActionORM)
                    .where(CallbackActionORM.public_id == public_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or row.consumed_at is not None:
                return False
            row.invalidated_at = self._now()
            row.invalidation_reason = str(reason)[:128]
            await session.flush()
            return True
