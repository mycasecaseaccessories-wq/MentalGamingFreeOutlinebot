"""Safe Outline management API client with certificate pinning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from app.models.outline_setup import OutlineCredentialInput, OutlineDiscoveryResult
from app.security.outline_tls import OutlineTLSIdentityError, verify_certificate_fingerprint

if TYPE_CHECKING:
    from app.security.outline_url_policy import ValidatedOutlineURL


class OutlineAPIError(RuntimeError):
    """Safe provider error; never contains the management URL."""


@dataclass(frozen=True, slots=True)
class OutlineClientConfig:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 10.0
    verify_timeout_seconds: float = 15.0


class OutlineAPIClient:
    def __init__(self, config: OutlineClientConfig | None = None) -> None:
        self.config = config or OutlineClientConfig()

    async def verify_management_api(
        self,
        url: ValidatedOutlineURL,
        credential: OutlineCredentialInput,
    ) -> OutlineDiscoveryResult:
        try:
            await verify_certificate_fingerprint(
                credential.management_url,
                credential.cert_sha256,
                timeout=self.config.connect_timeout_seconds,
            )
        except OutlineTLSIdentityError as exc:
            raise OutlineAPIError(str(exc)) from exc

        timeout = httpx.Timeout(
            self.config.verify_timeout_seconds,
            connect=self.config.connect_timeout_seconds,
            read=self.config.read_timeout_seconds,
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "MentalOutlineVPN-Setup/3.2",
        }
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            verify=True,
            headers=headers,
        ) as client:
            response = await self._get(client, url, "/server")
            if 300 <= response.status_code < 400:
                raise OutlineAPIError("Outline API redirect was rejected.")
            if response.status_code < 200 or response.status_code >= 300:
                raise OutlineAPIError("Outline API verification failed.")
            try:
                payload = response.json()
            except ValueError as exc:
                raise OutlineAPIError(
                    "Outline API returned an invalid response."
                ) from exc
            if not isinstance(payload, dict):
                raise OutlineAPIError("Outline API response is incompatible.")

            version = self._string(payload.get("version")) or self._string(
                payload.get("outlineVersion")
            )
            provider_id = self._string(payload.get("serverId")) or self._string(
                payload.get("id")
            )
            key_count: int | None = None
            try:
                keys = await self._get(client, url, "/access-keys")
                if 200 <= keys.status_code < 300:
                    body = keys.json()
                    if isinstance(body, dict) and isinstance(
                        body.get("accessKeys"), list
                    ):
                        key_count = len(body["accessKeys"])
                    elif isinstance(body, list):
                        key_count = len(body)
            except (httpx.HTTPError, ValueError, OutlineAPIError):
                key_count = None

            try:
                metrics = await self._get(client, url, "/metrics")
                metrics_available = 200 <= metrics.status_code < 300
            except (httpx.HTTPError, OutlineAPIError):
                metrics_available = False

            return OutlineDiscoveryResult(
                host=url.host,
                port=url.port,
                provider_server_id=provider_id,
                outline_version=version,
                api_compatible=True,
                existing_key_count=key_count,
                metrics_available=metrics_available,
                verified_at=datetime.now(UTC),
                safe_metadata={
                    "server_name": self._string(payload.get("name")),
                    "version": version,
                },
            )

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: ValidatedOutlineURL,
        endpoint: str,
    ) -> httpx.Response:
        try:
            return await client.get(
                f"{url.scheme}://{url.host}:{url.port}"
                f"{url.path.rstrip('/')}{endpoint}"
            )
        except httpx.TimeoutException as exc:
            raise OutlineAPIError("Outline API verification timed out.") from exc
        except httpx.HTTPError as exc:
            raise OutlineAPIError("Outline API connection failed.") from exc

    @staticmethod
    def _string(value: Any) -> str | None:
        return value.strip()[:64] if isinstance(value, str) and value.strip() else None
