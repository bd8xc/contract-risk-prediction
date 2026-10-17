"""Load extracted legal sections without treating editorial notes as provisions."""
from __future__ import annotations

import json
import re
from pathlib import Path


_EDITORIAL_HEADING = re.compile(
    r"^(?:for the statement of objects and reasons|see ss\.|subs\. by the)",
    re.IGNORECASE,
)


def load_legal_sections(path: str | Path) -> tuple[list[dict], list[str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("sections") or data.get("provisions") or []
    usable, excluded = [], []
    for row in rows:
        section = str(row.get("section", "")).strip()
        heading = str(row.get("heading", "")).strip()
        body = str(row.get("text", "")).strip()
        if not section or not heading or not body or _EDITORIAL_HEADING.match(heading):
            excluded.append(section or "unknown")
            continue
        usable.append(row)
    if not usable:
        raise ValueError(f"No usable legal provisions found in {path}")
    return usable, excluded
