import pytest

from app.services.notification_service import NotificationService


class _Bot:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("transient")
        return object()


class _Settings:
    admin_ids = (101, 202)


@pytest.mark.asyncio
async def test_operational_admin_delivery_routes_through_existing_bot():
    bot = _Bot()
    service = NotificationService(bot, settings=_Settings(), db=object())
    result = await service.notify_admins("safe operational alert")
    assert result["attempted"] == 2
    assert result["delivered"] == 2
    assert [call["chat_id"] for call in bot.calls] == [101, 202]


@pytest.mark.asyncio
async def test_operational_delivery_retries_transient_failures_and_returns_safe_result():
    bot = _Bot(failures=2)
    service = NotificationService(bot, settings=_Settings(), db=object())
    result = await service.send_message(101, "safe message")
    assert result["delivered"] is True
    assert result["attempts"] == 3
    assert all("transient" not in str(call) for call in bot.calls)
