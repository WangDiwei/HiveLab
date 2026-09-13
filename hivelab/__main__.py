"""HiveLab 命令行入口。

用法：
    python -m hivelab "帮我开发一个待办事项应用"   一次性提交需求
    python -m hivelab --demo                       使用内置模拟模型跑一次演示
    python -m hivelab --status <id>                查看项目状态
    python -m hivelab --gui                        启动桌面图形界面（阶段八）
    python -m hivelab --serve                      启动 Web API + 桌面端服务
    python -m hivelab                              交互式输入需求
"""

from __future__ import annotations

import argparse
import json
import sys

from hivelab.app.config import Settings, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hivelab", description="HiveLab —— 多 Agent 协作引擎 CLI"
    )
    parser.add_argument("requirement", nargs="?", help="用户需求文本")
    parser.add_argument("--gui", action="store_true", help="启动桌面图形界面")
    parser.add_argument(
        "--serve", action="store_true", help="启动后台 Web API 服务（供桌面端使用）"
    )
    parser.add_argument("--status", type=int, metavar="ID", help="查看指定项目状态")
    parser.add_argument("--env-file", help="指定 .env 配置文件路径")
    parser.add_argument("--demo", action="store_true", help="用内置模拟模型跑一次演示")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    return parser


def _orch(to_json: bool):
    from hivelab.app.workflows.orchestrator import Orchestrator

    settings = load_settings()
    return Orchestrator(settings)


def _print_report(report: dict, to_json: bool) -> None:
    if to_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print("=" * 60)
    print(f"项目 #{report.get('project_id')}  状态: {report.get('project_status')}")
    print(f"需求: {report.get('requirement')}")
    print(f"冒烟测试: {report.get('smoke', {}).get('status')}")
    print("执行 Agent:")
    for a in report.get("agents", []):
        if a.get("role_type") == "executer":
            print(f"  - {a['name']}")
    print("任务:")
    for t in report.get("tasks", []):
        print(f"  - [{t.get('status','')}] {t.get('name','')}")
    print(f"交付目录: {report.get('result_path', '')}")
    print("=" * 60)


def _run_status(project_id: int, to_json: bool) -> int:
    orch = _orch(to_json)
    try:
        status = orch.project_status(project_id)
        if status is None:
            print(f"未找到项目 {project_id}")
            return 1
        if to_json:
            print(json.dumps(status, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"项目 #{project_id} 状态: {status['status']}")
            for t in status.get("tasks", []):
                print(f"  - [{t['status']}] {t['name']}")
    finally:
        orch.close()
    return 0


def _run_one(requirement: str, to_json: bool, extra_langs: list[str] | None = None) -> int:
    orch = _orch(to_json)
    try:
        report = orch.submit(requirement, extra_langs=extra_langs)
        _print_report(report, to_json)
    finally:
        orch.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        from hivelab import __version__

        print(f"HiveLab {__version__}")
        return 0

    if args.gui:
        try:
            from hivelab.gui import run

            return run()
        except Exception as exc:  # GUI 依赖缺失时给出友好提示
            print(f"无法启动图形界面: {exc}")
            print("请确认已安装 PySide6。")
            return 1

    if args.status is not None:
        return _run_status(args.status, args.json)

    if args.serve:
        from hivelab.web import run_server

        return run_server()

    if args.requirement or args.demo:
        if args.requirement:
            req = args.requirement
        else:
            req = "请帮我开发一个待办事项应用"
        return _run_one(req, args.json)

    # 没有参数时默认启动桌面 GUI（面向普通用户）；无图形环境则退回交互模式
    try:
        from hivelab.gui import run

        return run()
    except Exception:
        pass

    # 交互模式
    print("HiveLab 交互模式 —— 输入需求，回车开始；输入 exit 退出。")
    while True:
        try:
            line = input("需求> ").strip()
        except EOFError:
            break
        if line.lower() in ("exit", "quit"):
            break
        if line:
            _run_one(line, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())