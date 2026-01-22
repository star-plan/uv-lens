from __future__ import annotations

from uv_lens.pyproject import extract_dependencies


def test_extract_dependencies_from_dict() -> None:
    """
    能从 dict 结构中正确抽取 project/dev/optional/build-system 依赖。
    """
    data = {
        "project": {
            "dependencies": ["httpx>=0.27"],
            "optional-dependencies": {"cli": ["rich>=13"]},
        },
        "dependency-groups": {"dev": ["pytest>=8"]},
        "build-system": {"requires": ["uv_build>=0.9.0,<0.10.0"]},
    }
    deps = extract_dependencies(data)
    assert [d.raw for d in deps.project] == ["httpx>=0.27"]
    assert [d.raw for d in deps.dev_groups["dev"]] == ["pytest>=8"]
    assert [d.raw for d in deps.optional["cli"]] == ["rich>=13"]
    assert [d.raw for d in deps.build_system] == ["uv_build>=0.9.0,<0.10.0"]
