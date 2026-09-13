"""模型配置面板：让普通用户一键填写 AI 服务商并立即生效。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...app.config.persistence import save_settings
from ...app.config.settings import ProviderMode, Settings
from ...web.app import WebService

_PROVIDER_LABELS = {
    "auto": "自动（配置了真实模型则用，否则用内置模拟）",
    "mock": "强制使用内置模拟（无需联网、无需密钥）",
    "real": "强制使用真实模型（必须填写服务商信息）",
}


class SettingsPanel(QWidget):
    """模型服务商配置：API 地址 / 密钥 / 模型名 / 运行模式。"""

    def __init__(self, svc: WebService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.svc = svc

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        kicker = QLabel("模型配置")
        kicker.setObjectName("moduleKicker")
        root.addWidget(kicker)

        title = QLabel("接上一个 AI 服务商")
        title.setObjectName("serifTitle")
        root.addWidget(title)

        desc = QLabel(
            "HiveLab 运行在任意 OpenAI 兼容的 API 上（如 OpenAI / DeepSeek / 通义 / 智谱 / "
            "本地 Ollama 等）。配置一次即保存在本机，之后直接使用。"
        )
        desc.setObjectName("hint")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # ---- 表单卡片 ----
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(20, 18, 20, 18)
        card_lay.setSpacing(12)
        root.addWidget(card)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)

        self._provider = QComboBox()
        for val, label in _PROVIDER_LABELS.items():
            self._provider.addItem(label, val)
        self._provider.setToolTip("运行模式")
        form.addRow("运行模式", self._provider)

        self._api_base = QLineEdit()
        self._api_base.setPlaceholderText("https://api.openai.com/v1 或 http://127.0.0.1:11434/v1")
        form.addRow("API 地址", self._api_base)

        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("sk-……")
        self._api_key.setEchoMode(QLineEdit.Password)
        form.addRow("API 密钥", self._api_key)

        self._model = QLineEdit()
        self._model.setPlaceholderText("gpt-4o-mini / deepseek-chat / qwen-turbo ……")
        form.addRow("模型名称", self._model)

        self._timeout = QSpinBox()
        self._timeout.setRange(10, 600)
        self._timeout.setValue(120)
        self._timeout.setSuffix(" 秒")
        form.addRow("请求超时", self._timeout)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(256, 32768)
        self._max_tokens.setValue(2048)
        self._max_tokens.setSingleStep(256)
        form.addRow("最大输出 Token", self._max_tokens)

        self._stream = QCheckBox("流式输出")
        form.addRow("流式", self._stream)
        card_lay.addLayout(form)

        self._hint_demo = QLabel(
            "不会配置？选择“强制使用内置模拟”后点击“保存并应用”，"
            "即可零配置体验完整协作流程（无需联网与密钥）。"
        )
        self._hint_demo.setObjectName("hint")
        self._hint_demo.setWordWrap(True)
        root.addWidget(self._hint_demo)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("保存并应用")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setObjectName("hint")
        self._status.setWordWrap(True)
        root.addWidget(self._status)
        root.addStretch(1)

        self._load_current()

    def _load_current(self) -> None:
        try:
            s: Settings = self.svc.orch().settings
        except Exception:
            s = Settings()
        idx = self._provider.findData(s.llm_provider.value if hasattr(s.llm_provider, "value") else str(s.llm_provider))
        if idx >= 0:
            self._provider.setCurrentIndex(idx)
        self._api_base.setText(s.llm_api_base or "")
        self._api_key.setText(s.llm_api_key or "")
        self._model.setText(s.llm_model or "")
        self._timeout.setValue(s.llm_timeout)
        self._max_tokens.setValue(s.llm_max_tokens)
        self._stream.setChecked(bool(s.llm_stream))
        gpt = "真实" if s.llm_api_key and s.llm_api_base else "内置模拟"
        self._status.setText(
            f"当前有效模式：{gpt}。{s.resolve_db_path} 已自动建好本地存储，无需手动处理。"
        )

    def _on_save(self) -> None:
        provider_val = self._provider.currentData() or "auto"
        provider = ProviderMode(provider_val)
        api_base = self._api_base.text().strip()
        api_key = self._api_key.text().strip()
        model = self._model.text().strip()

        if provider == ProviderMode.REAL and not (api_base and api_key and model):
            QMessageBox.warning(
                self, "配置不完整",
                "“强制使用真实模型”需要同时填写 API 地址、密钥和模型名称。",
            )
            return

        new_settings = Settings(
            llm_provider=provider,
            llm_api_base=api_base,
            llm_api_key=api_key,
            llm_model=model,
            llm_timeout=self._timeout.value(),
            llm_max_tokens=self._max_tokens.value(),
            llm_stream=self._stream.isChecked(),
        )

        path = save_settings(new_settings)
        self.svc.reload_settings(new_settings)
        self._status.setText(
            f"已保存并应用：{path}\n"
            f"当前模式={'真实模型' if provider == ProviderMode.REAL else ('内置模拟' if provider == ProviderMode.MOCK else '自动')}。"
        )

    def refresh(self) -> None:
        # 仅用于与 MainWindow 的轮询接口保持一致；配置面板无需实时刷新
        return None