"""Executable static audit for Phase 8.3 financial mutation boundaries."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "app" / "services"
ALLOWLIST = {"wallet_accounting_service.py"}
RULES = {
    "direct_wallet_assignment": re.compile(r"\b(?:wallet|row)\.balance\s*="),
    "legacy_adjust_call": re.compile(r"\.adjust_balance\s*\("),
    "callback_payment_success": re.compile(
        r"callback.*(?:paid|payment_success|payment_successful)|(?:paid|payment_success).*callback",
        re.IGNORECASE,
    ),
    "float_money_conversion": re.compile(
        r"float\s*\([^\n]*(?:amount|price|balance|currency)", re.IGNORECASE
    ),
}


def main() -> int:
    findings: list[tuple[str, int, str, str]] = []
    for path in sorted(SERVICES.rglob("*.py")):
        if path.name in ALLOWLIST or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for rule, pattern in RULES.items():
                if pattern.search(line):
                    findings.append((rule, number, str(path.relative_to(ROOT)), line.strip()))

    # Payment decisions from Telegram must be reachable only through the
    # signed callback path. Legacy unsigned confirmation branches must fail
    # closed and must never invoke the review service.
    admin_handler = ROOT / "app" / "handlers" / "admin.py"
    admin_source = admin_handler.read_text(encoding="utf-8").splitlines()
    for marker, call in (
        ("approve_confirm", "service.approve("),
        ("reject_confirm", "service.reject("),
    ):
        active = False
        for number, line in enumerate(admin_source, 1):
            if f'parts[2] == "{marker}"' in line:
                active = True
            elif active and line.startswith("        if "):
                active = False
            if active and call in line:
                findings.append(
                    (
                        "unsigned_payment_confirmation",
                        number,
                        str(admin_handler.relative_to(ROOT)),
                        line.strip(),
                    )
                )
    if findings:
        sys.stdout.write("UNSAFE FINANCIAL MATCHES:\n")
        for rule, number, path, line in findings:
            sys.stdout.write(f"{rule}: {path}:{number}: {line}\n")
        return 1
    sys.stdout.write("UNSAFE FINANCIAL MATCHES = 0\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
