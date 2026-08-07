"""
Security tests — detect leaked secrets and unsafe patterns in the codebase.

These tests scan source files to ensure:
  • No hardcoded tokens or API keys
  • No print() in production modules
  • No wildcard imports in production modules
  • Sensitive values are redacted in logs
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

# ── Paths ──────────────────────────────────────────────────────────────────────

_BOT_APP = Path(__file__).parent.parent.parent / "app"
_PROD_MODULES = list(_BOT_APP.rglob("*.py"))

# ── Patterns to detect ────────────────────────────────────────────────────────

# Matches real Telegram Bot token format: digits:base64
_BOT_TOKEN_PATTERN = re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}")

# Known test/placeholder token prefix — skip files that only contain this
_SAFE_TEST_PREFIX = "123456789:AAFake"

_HARDCODED_SECRET_PATTERNS = [
    re.compile(r'(?i)(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']'),
]

_WILDCARD_IMPORT = re.compile(r"^from\s+\S+\s+import\s+\*", re.MULTILINE)
_PRINT_STATEMENT = re.compile(r"(?<!\w)print\s*\(")


class TestSecretDetection:
    def test_no_real_bot_tokens_in_source(self) -> None:
        """Real Telegram bot tokens must never be committed to source code."""
        leaks: list[str] = []
        for path in _PROD_MODULES:
            content = path.read_text(errors="replace")
            # Skip test fixtures that intentionally contain fake tokens
            if _SAFE_TEST_PREFIX in content:
                continue
            for match in _BOT_TOKEN_PATTERN.finditer(content):
                leaks.append(f"{path.relative_to(_BOT_APP)}: {match.group()[:20]}…")
        assert not leaks, f"Possible real bot tokens found:\n" + "\n".join(leaks)

    def test_no_hardcoded_secrets_in_production_code(self) -> None:
        """No hardcoded password/secret/api_key/token literals in app/ modules."""
        leaks: list[str] = []
        for path in _PROD_MODULES:
            # Skip test files, fixtures, and example files
            rel = str(path)
            if any(skip in rel for skip in ["tests/", ".example", "conftest"]):
                continue
            content = path.read_text(errors="replace")
            for pattern in _HARDCODED_SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    leaks.append(f"{path.relative_to(_BOT_APP)}: {match.group()[:60]}")
        assert not leaks, (
            "Possible hardcoded secrets detected:\n" + "\n".join(leaks)
        )


class TestCodeStandards:
    def test_no_wildcard_imports_in_production_code(self) -> None:
        """Wildcard imports make namespaces unpredictable — ban them in app/."""
        violations: list[str] = []
        for path in _PROD_MODULES:
            rel = str(path)
            if any(skip in rel for skip in ["tests/", "alembic/", "__pycache__"]):
                continue
            content = path.read_text(errors="replace")
            if _WILDCARD_IMPORT.search(content):
                violations.append(str(path.relative_to(_BOT_APP)))
        assert not violations, (
            "Wildcard imports found in:\n" + "\n".join(violations)
        )

    def test_no_print_statements_in_production_code(self) -> None:
        """print() must not appear in production app/ modules (use logging)."""
        violations: list[str] = []
        for path in _PROD_MODULES:
            rel = str(path)
            # Skip test files and conftest — print is ok in tests
            if any(skip in rel for skip in ["tests/", "__pycache__"]):
                continue
            content = path.read_text(errors="replace")
            for lineno, line in enumerate(content.splitlines(), 1):
                # Skip comments and docstrings (rough heuristic)
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if _PRINT_STATEMENT.search(line):
                    violations.append(
                        f"{path.relative_to(_BOT_APP)}:{lineno}: {stripped[:80]}"
                    )
        assert not violations, (
            "print() found in production code:\n" + "\n".join(violations)
        )


class TestSensitiveLogRedaction:
    def test_redact_sensitive_removes_bot_token(self) -> None:
        from app.core.security import redact_sensitive

        token = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        result = redact_sensitive(f"Using token={token}")
        assert token not in result

    def test_redact_sensitive_removes_password(self) -> None:
        from app.core.security import redact_sensitive

        result = redact_sensitive("password=hunter2")
        assert "hunter2" not in result
        assert "***" in result

    def test_mask_database_url_hides_credentials(self) -> None:
        from app.core.security import mask_database_url

        url = "postgresql+asyncpg://admin:s3cr3t@db.internal:5432/vpn"
        masked = mask_database_url(url)
        assert "s3cr3t" not in masked
        assert "admin" not in masked
