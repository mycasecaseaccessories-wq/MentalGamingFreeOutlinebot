from __future__ import annotations

from datetime import datetime, timezone
import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Success
from app.events import EventType, bus
from app.services.base import BaseService
from app.services.referral_token_service import ReferralTokenService, StartPayloadParser
from app.services.settings_service import SettingsService
from app.services.referral_qualification_service import ReferralQualificationService
from database.models.referral import ReferralORM
from database.models.referral_token import ReferralTokenORM
from database.models.user import UserORM


class ReferralService(BaseService):
    """Authoritative attribution and read-only referral history service."""

    def __init__(self, db=None, token_service=None, settings_service=None):
        super().__init__(db)
        self.token_service = token_service or ReferralTokenService(db)
        self.settings = settings_service or SettingsService(db)

    async def is_enabled(self) -> bool:
        return bool(await self.settings.get("referral_enabled", True))

    async def personal_link(self, user_id: int, bot_username: str):
        token_result = await self.token_service.get_or_create_token(user_id)
        if token_result.is_failure:
            return token_result
        token = token_result.unwrap()
        return Success({"token": token, "link": self.token_service.build_referral_link(bot_username, token)})

    async def attribute(self, *, referrer_id: int, referred_id: int, token: str, source: str = ReferralORM.SOURCE_PERSONAL_LINK):
        if not await self.is_enabled():
            await bus.emit(EventType.REFERRAL_INVALID, referred_user_id=referred_id, result="disabled")
            return Success({"attributed": False, "reason": "disabled"})
        if referrer_id == referred_id:
            await bus.emit(EventType.REFERRAL_INVALID, referred_user_id=referred_id, result=ReferralORM.INVALID_SELF_REFERRAL)
            return Failure("self_referral", "You cannot use your own referral link.")
        resolved = await self.token_service.resolve_referrer(token)
        if resolved is None or resolved[1].id != referrer_id:
            await bus.emit(EventType.REFERRAL_INVALID, referred_user_id=referred_id, result=ReferralORM.INVALID_SOURCE)
            return Success({"attributed": False, "reason": "invalid_token"})
        require_new = bool(await self.settings.get("referral_require_new_user", True))
        first_wins = bool(await self.settings.get("referral_first_attribution_wins", True))
        async with self.db.session() as session:
            existing = (await session.execute(select(ReferralORM).where(ReferralORM.referred_id == referred_id))).scalar_one_or_none()
            if existing is not None:
                if first_wins or require_new:
                    return Success({"attributed": False, "reason": "already_attributed", "public_referral_id": existing.public_referral_id})
                return Failure("referrer_reassignment_forbidden", "Referral attribution cannot be replaced.")
            public_id = "REF-" + secrets.token_urlsafe(7).replace("_", "-").replace("/", "-")[:10].upper()
            row = ReferralORM(
                public_referral_id=public_id,
                referrer_id=referrer_id,
                referred_id=referred_id,
                token_id=resolved[0].id,
                status=ReferralORM.STATUS_PENDING_QUALIFICATION,
                source=source,
                safe_metadata={"attribution": "telegram_start"},
            )
            session.add(row)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                existing = (await session.execute(select(ReferralORM).where(ReferralORM.referred_id == referred_id))).scalar_one_or_none()
                return Success({"attributed": False, "reason": "already_attributed", "public_referral_id": getattr(existing, "public_referral_id", None)})
            result = {"attributed": True, "public_referral_id": row.public_referral_id, "status": row.status}
        await bus.emit(EventType.REFERRAL_ATTRIBUTED, referral_public_id=result["public_referral_id"], referrer_user_id=referrer_id, referred_user_id=referred_id, status=result["status"], source=source)
        return Success(result)

    async def attribute_from_start(self, *, referred_id: int, is_new_user: bool, raw_payload: str | None):
        parsed = StartPayloadParser.parse(raw_payload)
        if parsed["kind"] != "referral":
            return Success({"attributed": False, "reason": parsed["kind"]})
        token = parsed["token"]
        resolved = await self.token_service.resolve_referrer(token or "")
        if resolved is None:
            await bus.emit(EventType.REFERRAL_INVALID, referred_user_id=referred_id, result="unknown_token")
            return Success({"attributed": False, "reason": "invalid_token"})
        if not is_new_user:
            return Success({"attributed": False, "reason": "existing_user"})
        return await self.attribute(referrer_id=resolved[1].id, referred_id=referred_id, token=token or "")

    async def stats(self, referrer_id: int):
        async with self.db.session() as session:
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.referrer_id == referrer_id))).scalars().all())
        counts = {status: sum(1 for row in rows if row.status == status) for status in (
            ReferralORM.STATUS_PENDING_QUALIFICATION, ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED, ReferralORM.STATUS_INVALID,
        )}
        return Success({"total": len(rows), "pending": counts[ReferralORM.STATUS_PENDING_QUALIFICATION], "qualified": counts[ReferralORM.STATUS_QUALIFIED], "rewarded": counts[ReferralORM.STATUS_REWARDED], "invalid": counts[ReferralORM.STATUS_INVALID]})

    async def history(self, referrer_id: int, limit: int = 20):
        async with self.db.session() as session:
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.referrer_id == referrer_id).order_by(ReferralORM.created_at.desc()).limit(max(1, min(limit, 50))))).scalars().all())
        return Success({"items": [{"public_referral_id": row.public_referral_id, "friend_label": f"Friend #{index}", "status": row.status, "qualification_state": row.qualification_state, "review_required": row.review_required, "created_at": row.created_at} for index, row in enumerate(rows, 1)]})

    async def admin_stats(self):
        async with self.db.session() as session:
            rows = list((await session.execute(select(ReferralORM))).scalars().all())
        return Success({"total": len(rows), "pending": sum(row.status == ReferralORM.STATUS_PENDING_QUALIFICATION for row in rows), "qualified": sum(row.status == ReferralORM.STATUS_QUALIFIED for row in rows), "rewarded": sum(row.status == ReferralORM.STATUS_REWARDED for row in rows), "invalid": sum(row.status == ReferralORM.STATUS_INVALID for row in rows)})

    async def admin_recent(self, limit: int = 20):
        async with self.db.session() as session:
            rows = list((await session.execute(select(ReferralORM).order_by(ReferralORM.created_at.desc()).limit(max(1, min(limit, 50))))).scalars().all())
        return Success([{"public_referral_id": row.public_referral_id, "referrer_id": row.referrer_id, "referred_id": row.referred_id, "status": row.status, "qualification_state": row.qualification_state, "review_required": row.review_required, "risk_result": row.risk_result, "source": row.source, "created_at": row.created_at} for row in rows])

    async def admin_review_queue(self, limit: int = 50):
        async with self.db.session() as session:
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.review_required.is_(True), ReferralORM.status == ReferralORM.STATUS_PENDING_QUALIFICATION).order_by(ReferralORM.created_at.asc()).limit(max(1, min(50, limit))))).scalars().all())
        return Success([{"public_referral_id": row.public_referral_id, "referrer_id": row.referrer_id, "referred_id": row.referred_id, "qualification_state": row.qualification_state, "risk_result": row.risk_result, "created_at": row.created_at} for row in rows])

    async def review(self, *, actor_user_id: int, public_referral_id: str, decision: str, note: str = ""):
        if decision not in {"approve", "reject", "pending"}:
            return Failure("invalid_decision", "Invalid review decision.")
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or actor.role != "admin" or not actor.is_active:
                return Failure("permission_denied", "Admin permission required.")
            row = (await session.execute(select(ReferralORM).where(ReferralORM.public_referral_id == public_referral_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return Failure("not_found", "Referral not found.")
            if decision == "reject":
                row.status = ReferralORM.STATUS_INVALID
                row.qualification_state = ReferralORM.STATUS_INVALID
                row.invalidation_reason = ReferralORM.INVALID_ADMIN
                row.invalidated_at = datetime.now(timezone.utc)
            elif decision == "approve":
                row.review_required = False
                row.review_note = note[:256] or "admin_approved"
                row.qualification_state = ReferralORM.STATUS_QUALIFIED
                row.status = ReferralORM.STATUS_QUALIFIED
                row.qualified_at = datetime.now(timezone.utc)
            else:
                row.review_note = note[:256] or "kept_pending"
            await session.flush()
            result = {"public_referral_id": row.public_referral_id, "status": row.status, "qualification_state": row.qualification_state}
        if decision == "approve":
            await bus.emit(EventType.REFERRAL_QUALIFIED, referral_public_id=public_referral_id, reviewed=True)
        return Success(result)

    async def invalidate(self, *, actor_user_id: int, public_referral_id: str, reason: str):
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or actor.role != "admin" or not actor.is_active:
                return Failure("permission_denied", "Admin permission required.")
            row = (await session.execute(select(ReferralORM).where(ReferralORM.public_referral_id == public_referral_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return Failure("not_found", "Referral not found.")
            row.status = ReferralORM.STATUS_INVALID
            row.invalidated_at = datetime.now(timezone.utc)
            row.invalidation_reason = reason if reason in {ReferralORM.INVALID_SELF_REFERRAL, ReferralORM.INVALID_DUPLICATE_ATTRIBUTION, ReferralORM.INVALID_ABUSE, ReferralORM.INVALID_SOURCE, ReferralORM.INVALID_ADMIN, ReferralORM.INVALID_OTHER} else ReferralORM.INVALID_OTHER
        await bus.emit(EventType.REFERRAL_INVALIDATED, referral_public_id=public_referral_id, actor_user_id=actor_user_id, reason=row.invalidation_reason)
        return Success({"public_referral_id": public_referral_id, "status": ReferralORM.STATUS_INVALID})
