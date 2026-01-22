from __future__ import annotations

from packaging.requirements import Requirement
from packaging.version import Version

from uv_lens.models import CheckStatus
from uv_lens.versions import evaluate_requirement_against_latest, suggest_updated_requirement


def test_evaluate_exact_pin_up_to_date() -> None:
    """
    精确 pin 且等于最新版本时，应判定为 up_to_date。
    """
    req = Requirement("foo==1.0.0")
    ev = evaluate_requirement_against_latest(req, latest=Version("1.0.0"))
    assert ev.status == CheckStatus.UP_TO_DATE


def test_evaluate_range_allows_latest() -> None:
    """
    范围约束允许最新版本时，应判定为 upgrade_available。
    """
    req = Requirement("foo>=1")
    ev = evaluate_requirement_against_latest(req, latest=Version("2.0.0"))
    assert ev.status == CheckStatus.UPGRADE_AVAILABLE


def test_evaluate_blocks_latest_with_suggestion() -> None:
    """
    约束阻止最新版本时，应判定为 constraint_blocks_latest，并可给出写回建议。
    """
    req = Requirement("foo==1.0.0")
    ev = evaluate_requirement_against_latest(req, latest=Version("1.0.1"), pin="exact")
    assert ev.status == CheckStatus.CONSTRAINT_BLOCKS_LATEST
    assert ev.suggestion == "foo==1.0.1"


def test_suggest_compatible_upper_bound() -> None:
    """
    compatible pin 应生成一个简单的上界。
    """
    req = Requirement("foo")
    suggested = suggest_updated_requirement(req, latest=Version("2.3.4"), pin="compatible")
    assert suggested == "foo>=2.3.4,<3"
