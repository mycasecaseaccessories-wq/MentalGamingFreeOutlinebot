from __future__ import annotations

import secrets
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Success
from app.services.base import BaseService
from database.models.referral_token import ReferralTokenORM
from database.models.user import UserORM


class StartPayloadParser:
    """Parse namespaced Telegram /start payloads without breaking onboarding."""

    REFERRAL_PREFIX = "ref_"

    @classmethod
    def parse(cls, raw: str | None) -> dict[str, str | None]:
        value = (raw or "").strip()
        if not value:
            return {"kind": "normal", "token": None}
        if not value.startswith(cls.REFERRAL_PREFIX):
            return {"kind": "unknown", "token": None}
        token = value[len(cls.REFERRAL_PREFIX):]
        if not token or len(token) > 32 or not token.isalnum():
            return {"kind": "invalid_referral", "token": None}
        return {"kind": "referral", "token": token}


class ReferralTokenService(BaseService):
    """Issue stable, opaque, DB-unique personal referral tokens."""

    ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

    def generate_token(self, length: int = 8) -> str:
        return "".join(secrets.choice(self.ALPHABET) for _ in range(length))

    def validate_token_format(self, token: str | None) -> bool:
        return bool(token and 6 <= len(token) <= 32 and token.isalnum() and token.upper() == token)

    async def get_or_create_token(self, user_id: int):
        async with self.db.session() as session:
            existing = (await session.execute(select(ReferralTokenORM).where(ReferralTokenORM.user_id == user_id))).scalar_one_or_none()
            if existing is not None:
                return Success(existing.token)
            for _ in range(5):
                token = self.generate_token()
                if not self.validate_token_format(token):
                    continue
                session.add(ReferralTokenORM(user_id=user_id, token=token))
                try:
                    await session.flush()
                    return Success(token)
                except IntegrityError:
                    await session.rollback()
                    existing = (await session.execute(select(ReferralTokenORM).where(ReferralTokenORM.user_id == user_id))).scalar_one_or_none()
                    if existing is not None:
                        return Success(existing.token)
            return Failure("token_generation_failed", "Unable to create a referral token.")

    async def resolve_referrer(self, token: str):
        if not self.validate_token_format(token):
            return None
        async with self.db.session() as session:
            row = (await session.execute(
                select(ReferralTokenORM, UserORM)
                .join(UserORM, UserORM.id == ReferralTokenORM.user_id)
                .where(ReferralTokenORM.token == token)
            )).first()
            if row is None:
                return None
            token_row, user = row
            if not user.is_active or user.status in {"banned", "suspended", "inactive"}:
                return None
            return token_row, user

    @staticmethod
    def build_referral_link(bot_username: str, token: str) -> str:
        username = (bot_username or "").lstrip("@").strip()
        return f"https://t.me/{quote(username, safe='') }?start=ref_{quote(token, safe='') }"
