from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.models.vpn_provisioning import RemoteVPNKeyResult
from app.security.outline_tls import OutlineTLSIdentityError, verify_certificate_fingerprint
from app.security.outline_url_policy import validate_outline_url


class OutlineProviderError(RuntimeError):
    """Safe provider error; never contains management or access URLs."""


class OutlineProviderTimeout(OutlineProviderError):
    """Remote result is ambiguous; callers must not blindly retry."""


@dataclass(frozen=True, slots=True)
class OutlineProviderConfig:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0


class OutlineProvider:
    provider_name = "outline"

    def __init__(self, *, config: OutlineProviderConfig | None = None) -> None:
        self.config = config or OutlineProviderConfig()

    async def create_key(
        self,
        *,
        management_url: str,
        name: str,
        expected_cert_sha256: str | None = None,
    ) -> RemoteVPNKeyResult:
        validated = await validate_outline_url(management_url, allow_private=True)
        try:
            await verify_certificate_fingerprint(
                management_url,
                expected_cert_sha256,
                timeout=self.config.connect_timeout_seconds,
            )
        except OutlineTLSIdentityError as exc:
            raise OutlineProviderError("Outline server identity verification failed.") from exc
        timeout = httpx.Timeout(
            self.config.read_timeout_seconds,
            connect=self.config.connect_timeout_seconds,
            read=self.config.read_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=timeout,
                verify=True,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "MentalOutlineVPN-Provision/4.1",
                },
            ) as client:
                response = await client.post(
                    f"{validated.scheme}://{validated.host}:{validated.port}{validated.path.rstrip('/')}/access-keys",
                    json={"name": name},
                )
        except httpx.TimeoutException as exc:
            raise OutlineProviderTimeout(
                "Outline key creation timed out; remote outcome is unknown."
            ) from exc
        except httpx.HTTPError as exc:
            raise OutlineProviderError("Outline provider connection failed.") from exc
        if response.status_code in {401, 403}:
            raise OutlineProviderError("Outline provider authentication failed.")
        if response.status_code < 200 or response.status_code >= 300:
            raise OutlineProviderError("Outline key creation was rejected by the provider.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise OutlineProviderError(
                "Outline provider returned an invalid key response."
            ) from exc
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("id"), int)
            or not isinstance(payload.get("accessUrl"), str)
            or not payload["accessUrl"]
        ):
            raise OutlineProviderError(
                "Outline provider returned an incompatible key response."
            )
        return RemoteVPNKeyResult(
            int(payload["id"]),
            payload["accessUrl"],
            self.provider_name,
            datetime.now(UTC),
            {"name": name},
        )

    async def delete_key(
        self,
        *,
        management_url: str,
        provider_key_id: int,
        expected_cert_sha256: str | None = None,
    ) -> None:
        validated = await validate_outline_url(management_url, allow_private=True)
        try:
            await verify_certificate_fingerprint(
                management_url,
                expected_cert_sha256,
                timeout=self.config.connect_timeout_seconds,
            )
        except OutlineTLSIdentityError as exc:
            raise OutlineProviderError("Outline server identity verification failed.") from exc
        timeout = httpx.Timeout(
            self.config.read_timeout_seconds,
            connect=self.config.connect_timeout_seconds,
            read=self.config.read_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=timeout,
                verify=True,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MentalOutlineVPN-Provision/4.1",
                },
            ) as client:
                response = await client.delete(
                    f"{validated.scheme}://{validated.host}:{validated.port}{validated.path.rstrip('/')}/access-keys/{int(provider_key_id)}"
                )
        except httpx.TimeoutException as exc:
            raise OutlineProviderTimeout("Outline compensation delete timed out.") from exc
        except httpx.HTTPError as exc:
            raise OutlineProviderError("Outline compensation connection failed.") from exc
        if response.status_code not in {200, 204, 404}:
            raise OutlineProviderError(
                "Outline compensation delete was rejected by the provider."
            )

    @staticmethod
    def safe_key_name(*, public_order_id: str | None, operation_id: str) -> str:
        identity = public_order_id or operation_id
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return f"MG-ORD-{suffix}"
