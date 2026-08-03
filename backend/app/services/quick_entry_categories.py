from __future__ import annotations

import re

_PARENT_SUB_RE = re.compile(r"^(.+?)\s*[:：]\s*(.+)$")


def strip_parent_category(raw: str | None) -> str | None:
    if raw is None:
        return None
    match = _PARENT_SUB_RE.match(raw.strip())
    if match is None:
        return raw.strip()
    return match.group(2).strip()
