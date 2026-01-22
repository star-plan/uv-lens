from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from packaging.requirements import Requirement


class DependencyKind(str, Enum):
    """
    依赖来源类别。
    """

    PROJECT = "project"
    DEV_GROUP = "dev_group"
    OPTIONAL = "optional"
    BUILD_SYSTEM = "build_system"


@dataclass(frozen=True, slots=True)
class DependencyItem:
    """
    从 pyproject.toml 中抽取出来的一条依赖项（保留原始字符串与解析结果）。
    """

    kind: DependencyKind
    group: str
    raw: str
    requirement: Requirement | None
    error: str | None


class CheckStatus(str, Enum):
    """
    单个依赖项的检查状态。
    """

    UP_TO_DATE = "up_to_date"
    UPGRADE_AVAILABLE = "upgrade_available"
    CONSTRAINT_BLOCKS_LATEST = "constraint_blocks_latest"
    UNPINNED = "unpinned"
    NOT_FOUND = "not_found"
    INVALID_REQUIREMENT = "invalid_requirement"
    NETWORK_ERROR = "network_error"
    INDEX_ERROR = "index_error"


PinMode = Literal["none", "compatible", "exact"]
