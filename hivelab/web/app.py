"""FastAPI 服务。

复用 Orchestrator 核心。submit 在后台线程运行，返回 project_id，
调用方可通过 GET /api/projects/{id}/delivery 轮询结果。
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..app.config import Settings, load_settings
from ..app.config.persistence import apply_user_settings
from ..app.workflows.orchestrator import Orchestrator


class SubmitRequest(BaseModel):
    requirement: str
    extra_langs: list[str] | None = None


class RunRecord(BaseModel):
    project_id: int
    running: bool
    report: dict[str, Any] | None = None
    error: str | None = None


class WebService:
    """包装 Orchestrator，提供线程安全的提交与查询。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._orch: Orchestrator | None = None
        self._lock = threading.Lock()
        self._records: dict[int, RunRecord] = {}

    def orch(self) -> Orchestrator:
        with self._lock:
            if self._orch is None:
                self._orch = Orchestrator(self._settings)
            return self._orch

    def submit(self, requirement: str, extra_langs: list[str] | None = None) -> int:
        repo = self.orch().repo
        project_id = repo.create_project(requirement, status="created")
        rec = RunRecord(project_id=project_id, running=True)
        with self._lock:
            self._records[project_id] = rec

        orch = self._orch

        def _run() -> None:
            try:
                report = orch.submit(requirement, extra_langs=extra_langs)
                # 报告中 project_id 用记录的 id 覆盖（保持一致）
                report["project_id"] = project_id
                with self._lock:
                    rec.running = False
                    rec.report = report
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    rec.running = False
                    rec.error = str(exc)

        threading.Thread(target=_run, daemon=True).start()
        return project_id

    def record(self, project_id: int) -> RunRecord | None:
        with self._lock:
            return self._records.get(project_id)

    def reload_settings(self, settings: Settings) -> None:
        """替换配置并重建编排器（供桌面端“模型配置”页保存后立即生效）。

        正在后台运行的项目持有旧编排器引用，不受影响；新需求用新配置。
        """
        with self._lock:
            self._settings = settings
            self._orch = Orchestrator(settings)

    # ---- 查询便捷方法（空跑不会新建） ----
    def status(self, project_id: int) -> dict | None:
        repo = self.orch().repo
        p = repo.get_project(project_id)
        if p is None:
            return None
        p["tasks"] = repo.list_tasks(project_id)
        p["agents"] = repo.list_agents(project_id)
        return p

    def list_projects(self) -> list[dict]:
        return self.orch().repo.list_projects()

    def list_agents(self) -> list[dict]:
        return self.orch().repo.list_agents()

    def list_tasks(self, project_id: int | None = None) -> list[dict]:
        return self.orch().repo.list_tasks(project_id)

    def list_dm(self, agent_id: int) -> list[dict]:
        return self.orch().repo.list_direct_messages_for(agent_id)

    def list_chats(self) -> list[dict]:
        return self.orch().repo.list_group_chats()

    def list_logs(self, limit: int = 100) -> list[dict]:
        return self.orch().repo.list_events(limit=limit)

    def list_errors(self, limit: int = 100) -> list[dict]:
        return self.orch().repo.list_error_logs(limit=limit)

    def delivery(self, project_id: int) -> dict:
        run = self.record(project_id)
        if run is not None and run.error:
            return {"project_id": project_id, "status": "error", "error": run.error}
        if run is not None and run.report:
            return run.report
        status = self.status(project_id) or {}
        return status


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or apply_user_settings(load_settings())
    svc = WebService(settings)

    app = FastAPI(title="HiveLab", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.svc = svc

    @app.post("/api/projects")
    def submit(req: SubmitRequest) -> dict:
        if not (req.requirement or "").strip():
            raise HTTPException(400, "需求不能为空")
        project_id = svc.submit(req.requirement, req.extra_langs)
        return {"project_id": project_id, "status": "running"}

    @app.get("/api/projects")
    def projects() -> list[dict]:
        return svc.list_projects()

    @app.get("/api/projects/{project_id}")
    def project(project_id: int) -> dict:
        status = svc.status(project_id)
        if status is None:
            raise HTTPException(404, "项目不存在")
        return status

    @app.get("/api/projects/{project_id}/delivery")
    def delivery(project_id: int) -> dict:
        return svc.delivery(project_id)

    @app.get("/api/tasks")
    def tasks(project_id: int | None = None) -> list[dict]:
        return svc.list_tasks(project_id)

    @app.get("/api/agents")
    def agents() -> list[dict]:
        return svc.list_agents()

    @app.get("/api/agents/{agent_id}/messages")
    def agent_messages(agent_id: int) -> list[dict]:
        return svc.list_dm(agent_id)

    @app.get("/api/chats")
    def chats() -> list[dict]:
        return svc.list_chats()

    @app.get("/api/logs")
    def logs(limit: int = 100) -> list[dict]:
        return svc.list_logs(limit)

    @app.get("/api/errors")
    def errors(limit: int = 100) -> list[dict]:
        return svc.list_errors(limit)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "mock": svc.orch().llm.is_mock}

    return app


def run_server(host: str = "127.0.0.1", port: int = 8357) -> int:
    """启动 uvicorn（供 --serve 与桌面端调用）。"""
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0