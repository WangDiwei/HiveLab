"""需求 & 项目面板：用一句话描述需求，即可启动整个多智体协作流程。

设计定位（参考 minimalist-skill / emil-design-eng）：
- 分层排版：模块小标（kicker）→ 编辑风衬线大标题 → 说明文字。
- 卡式布局：输入区与报告区各自放进 1px 微边框的卡片容器，大留白。
- 无 emoji：状态以文字 + 语义色传达。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...web.app import WebService


class _Card(QFrame):
    """1px 微边框卡片容器。"""

    def __init__(self, alt: bool = False) -> None:
        super().__init__()
        self.setObjectName("cardAlt" if alt else "card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 16, 18, 16)
        self._lay.setSpacing(10)

    def body(self) -> QVBoxLayout:
        return self._lay


class RequirementPanel(QWidget):
    """让普通人用一句话描述需求，即可启动整个多智体协作流程。"""

    def __init__(self, svc: WebService) -> None:
        super().__init__()
        self.svc = svc
        self._active_pid: int | None = None
        self._last_shown_report: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        # ---- 标题区（分层排版） ----
        kicker = QLabel("需求 · 项目")
        kicker.setObjectName("moduleKicker")
        root.addWidget(kicker)

        title = QLabel("把你的想法，交给一个智体团队")
        title.setObjectName("serifTitle")
        root.addWidget(title)

        hint = QLabel(
            "用自然语言描述你要什么即可。规划者会拆解任务、多个执行智体分工协作，"
            "最后交付者整理完成结果与文档给你。"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setAlignment(kicker.alignment())
        root.addWidget(hint)

        # ---- 输入卡片 ----
        card = _Card()
        root.addWidget(card)
        body = card.body()

        sec = QLabel("需求描述")
        sec.setObjectName("sectionLabel")
        body.addWidget(sec)

        self._req = QPlainTextEdit()
        self._req.setPlaceholderText("例如：开发一个待办事项应用；帮我写一份产品周报；做一个爬取指定网站的小工具。")
        self._req.setMinimumHeight(96)
        body.addWidget(self._req)

        langs_row = QHBoxLayout()
        langs_row.setSpacing(8)
        langs_row.addWidget(QLabel("额外文档语言（可选，逗号分隔）"))
        self._langs = QLineEdit()
        self._langs.setPlaceholderText("如：en, ja，留空则仅中文")
        langs_row.addWidget(self._langs, 1)
        body.addLayout(langs_row)

        # ---- 操作栏：启动按钮 + 项目选择 ----
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self._submit_btn = QPushButton("启动智体协作")
        self._submit_btn.clicked.connect(self._on_submit)
        op_row.addWidget(self._submit_btn)

        op_row.addStretch(1)
        op_row.addWidget(QLabel("查看项目"))
        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(300)
        self._project_combo.currentIndexChanged.connect(self._on_project_selected)
        op_row.addWidget(self._project_combo)
        root.addLayout(op_row)

        self._status = QLabel("就绪。")
        self._status.setObjectName("hint")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # ---- 报告卡片 ----
        report_card = _Card(alt=True)
        root.addWidget(report_card, 1)
        rep_body = report_card.body()
        rep_sec = QLabel("项目快照 / 交付报告")
        rep_sec.setObjectName("sectionLabel")
        rep_body.addWidget(rep_sec)

        self._report = QTextBrowser()
        self._report.setObjectName("reportBrowser")
        self._report.setOpenExternalLinks(True)
        rep_body.addWidget(self._report, 1)

        self.refresh()

    def _on_submit(self) -> None:
        requirement = self._req.toPlainText().strip()
        if not requirement:
            QMessageBox.warning(self, "提示", "请先填写需求描述。")
            return

        langs: list[str] | None = None
        text = self._langs.text().strip()
        if text:
            langs = [x.strip() for x in text.split(",") if x.strip()]

        try:
            pid = self.svc.submit(requirement, extra_langs=langs)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "启动失败", str(exc))
            return

        self._active_pid = pid
        self._last_shown_report = None
        self._status.setText(f"项目 #{pid} 已启动，智体团队正在协作中……")
        self._report.setPlainText("智体团队已开始工作，请稍候，正在规划、执行并交付……")
        self._submit_btn.setEnabled(False)
        self._refresh_projects_combo(select=pid)
        self._poll_running()

    def _on_project_selected(self) -> None:
        pid = self._project_combo.currentData()
        if pid is not None:
            self._active_pid = pid
            self._render(force=True)

    def _refresh_projects_combo(self, select: int | None = None) -> None:
        current = self._project_combo.currentData()
        try:
            projects = self.svc.list_projects()
        except Exception:
            return
        if not projects:
            self._project_combo.clear()
            return
        prev = self._project_combo.blockSignals(True)
        self._project_combo.clear()
        for p in projects:
            label = f"#{p['id']}  {self._shorten(p.get('requirement', ''))}  [{p.get('status', '')}]"
            self._project_combo.addItem(label, p["id"])
        target = select if select is not None else current
        if target is not None:
            idx = self._project_combo.findData(target)
            if idx >= 0:
                self._project_combo.setCurrentIndex(idx)
        self._project_combo.blockSignals(prev)

    @staticmethod
    def _shorten(text: str, n: int = 18) -> str:
        text = (text or "").replace("\n", " ")
        return text if len(text) <= n else text[: n - 1] + "…"

    def _poll_running(self) -> None:
        if self._active_pid is None:
            return
        try:
            rec = self.svc.record(self._active_pid)
        except Exception:
            return
        if rec is not None and not rec.running and rec.report:
            self._submit_btn.setEnabled(True)
            self._render_report(rec.report)
        else:
            pass  # 由 MainWindow._timer 周期性 refresh 驱动

    # ---- 供 MainWindow 轮询调用 ----
    def refresh(self) -> None:
        self._refresh_projects_combo()
        if self._active_pid is not None:
            rec = self.svc.record(self._active_pid)
            if rec is not None and rec.running:
                self._status.setText(
                    f"项目 #{self._active_pid} 运行中，动作：{rec.report and '完成' or '执行中'}…"
                )
                self._render(force=False)
                return
            if rec is not None and rec.report:
                if rec.report != self._last_shown_report:
                    self._submit_btn.setEnabled(True)
                    self._render_report(rec.report)
                    self._last_shown_report = rec.report
                return
            if rec is not None and rec.error:
                self._submit_btn.setEnabled(True)
                self._status.setText(f"运行失败：{rec.error}")
                self._report.setPlainText(f"运行出错：\n{rec.error}")
                return
        self._render(force=False)

    def _render(self, force: bool) -> None:
        if self._active_pid is None:
            self._report.setPlainText("尚未选择项目。提交需求或从上方选择一个项目查看。")
            return

        try:
            status = self.svc.status(self._active_pid)
        except Exception:
            return
        if not status:
            return
        tasks = status.get("tasks", [])
        agents = status.get("agents", [])
        pstatus = status.get("status", "")

        lines = [
            f"项目 #{status.get('id')}  状态：{pstatus}",
            f"需求：{status.get('requirement', '')}",
            "",
            f"智体数量：{len(agents)}    任务数量：{len(tasks)}",
        ]
        if tasks:
            done = sum(1 for t in tasks if t.get("status") == "completed")
            lines.append(f"已完成任务：{done}/{len(tasks)}")
        lines.append("")
        if tasks:
            for t in tasks:
                mark = "已完成" if t.get("status") == "completed" else (
                    "进行中" if t.get("status") in ("in_progress", "assigned") else "待处理"
                )
                lines.append(f"[{mark}] {t.get('name')}")
        self._report.setPlainText("\n".join(lines))

    def _render_report(self, report: dict) -> None:
        smoke = report.get("smoke", {})
        smoke_ok = smoke.get("status") == "PASS"
        html = [
            "<h3>交付完成</h3>",
            f"<p><b>项目：</b>{report.get('project_name', '')} &nbsp;"
            f"<b>状态：</b>{report.get('project_status', '')}</p>",
            f"<p><b>需求：</b>{self._html_escape(report.get('requirement', ''))}</p>",
            f"<p><b>智体数量：</b>{report.get('executer_count', 0) + 1} &nbsp;"
            f"<b>任务数量：</b>{len(report.get('tasks', []))}</p>",
            f"<p><b>冒烟测试：</b>"
            f"<span style='color:{'#2F5B9E' if smoke_ok else '#8A6508'}'>"
            f"{smoke.get('status', 'N/A')}</span> — {self._html_escape(smoke.get('summary', ''))}</p>",
        ]
        tasks = report.get("tasks", [])
        if tasks:
            html.append("<br><b>任务完成情况：</b><ul>")
            for t in tasks:
                mark = "已完成" if t.get("status") == "completed" else "待处理"
                html.append(f"<li>{mark} · {self._html_escape(t.get('name', ''))}</li>")
            html.append("</ul>")

        result_path = report.get("result_path")
        if result_path:
            html.append(f"<p><b>产物目录：</b>{self._html_escape(result_path)}</p>")
        readmes = report.get("readmes")
        if readmes:
            html.append("<p><b>文档：</b></p><ul>")
            for p in readmes:
                html.append(f"<li>{self._html_escape(str(p))}</li>")
            html.append("</ul>")

        self._status.setText(f"项目 #{report.get('project_id')} 已交付")
        self._report.setHtml("<br>".join(html))

    @staticmethod
    def _html_escape(text: str) -> str:
        import html as _html

        return _html.escape(text or "")