from __future__ import annotations

import re
from pathlib import Path


PRODUCTION_ROOTS = (Path("bot/app"), Path("bot/config"), Path("bot/database"))
UNSAFE_PATTERNS = (
    re.compile(r"role\s*==\s*(['\"])admin\1"),
    re.compile(r"role\s*!=\s*(['\"])admin\1"),
    re.compile(r"maintenance_bypass"),
    re.compile(r"actor\.is_admin"),
    re.compile(r"(['\"])is_admin\1\s*:\s*True"),
)


def test_no_direct_privileged_bypass_patterns_in_production_source() -> None:
    matches: list[str] = []
    for root in PRODUCTION_ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in UNSAFE_PATTERNS:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    matches.append(f"{path}:{line}: {match.group(0)}")
    assert matches == [], "UNSAFE privileged authorization matches:\n" + "\n".join(matches)
