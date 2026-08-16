from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_translations(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for node in tree.body:
        value_node = None
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TRANSLATIONS" for t in node.targets):
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "TRANSLATIONS":
            value_node = node.value
        if isinstance(value_node, ast.Dict):
            result.update(ast.literal_eval(value_node))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "TRANSLATIONS" and call.func.attr == "update" and call.args and isinstance(call.args[0], ast.Dict):
                result.update(ast.literal_eval(call.args[0]))
    if not result:
        raise RuntimeError(f"TRANSLATIONS not found in {path}")
    return result

def callsite_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "bot" / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and (arg.value.startswith("referral.") or arg.value.startswith("admin.referrals")):
                    keys.add(arg.value)
    return keys

def placeholders(value: str) -> set[str]:
    import string
    return {field_name for _, field_name, _, _ in string.Formatter().parse(value) if field_name}

en = load_translations(ROOT / "bot/locales/en/__init__.py")
my = load_translations(ROOT / "bot/locales/my/__init__.py")
referral_keys = sorted({key for key in en | my if key.startswith("referral.") or key.startswith("admin.referrals")})
called = sorted(callsite_keys())
report = {
    "english_keys": sorted(key for key in en if key.startswith("referral.") or key.startswith("admin.referrals")),
    "myanmar_keys": sorted(key for key in my if key.startswith("referral.") or key.startswith("admin.referrals")),
    "missing_in_english": sorted(key for key in referral_keys if key not in en),
    "missing_in_myanmar": sorted(key for key in referral_keys if key not in my),
    "called_but_missing_in_english": sorted(key for key in called if key not in en),
    "called_but_missing_in_myanmar": sorted(key for key in called if key not in my),
    "placeholder_mismatches": [],
    "strings": {},
}
for key in referral_keys:
    if key in en and key in my:
        en_ph = sorted(placeholders(en[key]))
        my_ph = sorted(placeholders(my[key]))
        if en_ph != my_ph:
            report["placeholder_mismatches"].append({"key": key, "en": en_ph, "my": my_ph})
        report["strings"][key] = {"en": en[key], "my": my[key], "en_chars": len(en[key]), "my_chars": len(my[key])}
print(json.dumps(report, ensure_ascii=False, indent=2))
