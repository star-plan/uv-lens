from __future__ import annotations

import re

_NORMALIZE_RE = re.compile(r"[-_.]+")


def normalize_project_name(name: str) -> str:
    """
    将包名按 PEP 503 规则规范化（用于缓存键与对比）。
    """
    return _NORMALIZE_RE.sub("-", name).lower()
