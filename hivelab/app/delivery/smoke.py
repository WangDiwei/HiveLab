"""冒烟测试引擎：对产出项目做基本可用性校验。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SmokeResult:
    """冒烟测试结果。"""

    status: str  # PASS / FAIL
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def summary(self) -> str:
        passed = sum(1 for c in self.checks if c["passed"])
        total = len(self.checks)
        lines = [f"冒烟测试通过 {passed}/{total} 项："]
        for c in self.checks:
            mark = "✓" if c["passed"] else "✗"
            lines.append(f"  {mark} {c['name']}: {c['detail']}")
        return "\n".join(lines)


class SmokeTester:
    """校验交付项目的基本可用性。"""

    def run(self, meta: dict[str, Any], project_dir: Path) -> SmokeResult:
        result = SmokeResult(status="PASS")
        # 1) 项目目录存在
        self._check(result, "项目目录存在", project_dir.exists(), str(project_dir))
        # 2) 至少一个产物
        artifacts = meta.get("artifacts", [])
        self._check(result, "存在项目产物", len(artifacts) > 0, f"{len(artifacts)} 个")
        # 3) 所有任务均为完成态
        tasks = meta.get("tasks", [])
        all_done = all(t.get("status") == "completed" for t in tasks)
        self._check(result, "所有任务已交付", all_done,
                    "; ".join(f"{t.get('name','')}={t.get('status','')}" for t in tasks) or "无任务")
        # 4) README 文件已被生成
        readmes = list((project_dir / "readmes").glob("README*.md")) if (project_dir / "readmes").exists() else []
        self._check(result, "已生成 README", len(readmes) >= 1,
                    ", ".join(r.name for r in readmes) or "未找到")
        # 5) 产物文件真实存在
        files_exist = all(a["path"] and Path(a["path"]).exists() for a in artifacts)
        self._check(result, "产物文件可访问", files_exist, f"{len(artifacts)} 个产物文件")
        result.status = "PASS" if all(c["passed"] for c in result.checks) else "FAIL"
        return result

    @staticmethod
    def _check(result: SmokeResult, name: str, passed: bool, detail: str) -> None:
        result.checks.append({"name": name, "passed": bool(passed), "detail": detail})