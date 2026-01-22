from __future__ import annotations

from dataclasses import dataclass

from packaging.requirements import Requirement
from packaging.specifiers import Specifier
from packaging.version import Version

from uv_lens.models import CheckStatus, PinMode


@dataclass(frozen=True, slots=True)
class VersionEvaluation:
    """
    版本对比的结果（状态 + 建议）。
    """

    status: CheckStatus
    latest: Version | None
    suggestion: str | None
    reason: str | None


def _format_requirement(name: str, *, extras: set[str], spec: str, marker: str | None) -> str:
    """
    将 name/extras/spec/marker 重新组合成 PEP 508 requirement 字符串。
    """
    extras_part = f"[{','.join(sorted(extras))}]" if extras else ""
    marker_part = f"; {marker}" if marker else ""
    return f"{name}{extras_part}{spec}{marker_part}"


def _next_compatible_upper_bound(latest: Version) -> str:
    """
    基于最新版本生成一个简单的“兼容上界”。
    """
    if latest.major == 0:
        return f"<0.{latest.minor + 1}"
    return f"<{latest.major + 1}"


def suggest_updated_requirement(req: Requirement, *, latest: Version, pin: PinMode) -> str | None:
    """
    基于现有 requirement 与最新版本生成建议的 requirement 字符串。
    """
    if req.url:
        return None

    marker = str(req.marker) if req.marker else None
    name = req.name
    extras = set(req.extras)

    if pin == "none":
        return None

    if pin == "exact":
        return _format_requirement(name, extras=extras, spec=f"=={latest}", marker=marker)

    if pin == "compatible":
        upper = _next_compatible_upper_bound(latest)
        return _format_requirement(name, extras=extras, spec=f">={latest},{upper}", marker=marker)

    return None


def evaluate_requirement_against_latest(
    req: Requirement | None,
    *,
    latest: Version | None,
    not_found: bool = False,
    network_error: str | None = None,
    pin: PinMode = "none",
) -> VersionEvaluation:
    """
    将当前 requirement 的版本约束与最新版本进行对比并生成状态与建议。
    """
    if req is None:
        return VersionEvaluation(
            status=CheckStatus.INVALID_REQUIREMENT,
            latest=latest,
            suggestion=None,
            reason="invalid requirement",
        )

    if network_error:
        return VersionEvaluation(
            status=CheckStatus.NETWORK_ERROR,
            latest=latest,
            suggestion=None,
            reason=network_error,
        )

    if not_found:
        return VersionEvaluation(
            status=CheckStatus.NOT_FOUND,
            latest=latest,
            suggestion=None,
            reason="package not found",
        )

    if latest is None:
        return VersionEvaluation(
            status=CheckStatus.INDEX_ERROR,
            latest=None,
            suggestion=None,
            reason="no latest version resolved",
        )

    if not req.specifier:
        return VersionEvaluation(
            status=CheckStatus.UNPINNED,
            latest=latest,
            suggestion=suggest_updated_requirement(req, latest=latest, pin=pin),
            reason=None,
        )

    if latest in req.specifier:
        status = CheckStatus.UPGRADE_AVAILABLE
        if contains_exact_pin(req):
            status = CheckStatus.UP_TO_DATE

        return VersionEvaluation(
            status=status,
            latest=latest,
            suggestion=None,
            reason=None,
        )

    return VersionEvaluation(
        status=CheckStatus.CONSTRAINT_BLOCKS_LATEST,
        latest=latest,
        suggestion=suggest_updated_requirement(req, latest=latest, pin=pin),
        reason=None,
    )


def contains_exact_pin(req: Requirement) -> bool:
    """
    判断 requirement 是否包含精确 pin（== 或 ===）。
    """
    return any(s.operator in {"==", "==="} for s in req.specifier)


def has_upper_bound(req: Requirement) -> bool:
    """
    判断 requirement 是否包含上界（< 或 <=）。
    """
    return any(s.operator in {"<", "<="} for s in req.specifier)


def find_upper_bound(req: Requirement) -> Specifier | None:
    """
    找到 requirement 中的第一个上界 Specifier（< 或 <=）。
    """
    for spec in req.specifier:
        if spec.operator in {"<", "<="}:
            return spec
    return None
