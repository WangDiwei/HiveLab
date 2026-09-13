# 🐝 HiveLab

> A virtual software company on your desktop — where a team of AI agents plans, builds, and delivers projects together.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-contributing)
[![GitHub stars](https://img.shields.io/github/stars/WangDiwei/HiveLab?style=social)](https://github.com/WangDiwei/HiveLab/stargazers)

**HiveLab** turns a plain-language requirement into a delivered project by simulating a small software company: a **Planner Agent** breaks the requirement into tasks, multiple **Executor Agents** carry them out while chatting and coordinating in a shared message hub, and a **Deliverer Agent** runs smoke tests, packages artifacts, and generates multilingual READMEs.

Everything runs locally on your machine — SQLite storage, an embedded FastAPI service, and a polished PySide6 desktop UI. Works fully offline thanks to a built-in mock LLM, or plug in any OpenAI-compatible API.

---

## ✨ Features

- 🏢 **Virtual company simulation** — Planner → Executors → Deliverer, with roles, task assignment, priorities, and dependencies
- 💬 **Agent collaboration** — a group chat + direct-message hub lets agents coordinate, mention each other, and escalate blockers
- 🔁 **Self-healing workflow** — the orchestrator monitors for failed/blocked tasks and retries or reassigns automatically
- 🖥️ **Desktop GUI** — requirement submission, agent chat viewer, task kanban, live logs, and model settings
- 🔌 **Any OpenAI-compatible LLM** — configure `api_base`, `key`, and `model`; no SDK lock-in
- 🧪 **Offline demo mode** — a built-in `MockLLM` runs the entire pipeline with zero configuration
- 📦 **Real deliverables** — generated artifacts, smoke-test reports, and READMEs in English, Chinese, and more
- ⚙️ **REST API** — a FastAPI service backs the GUI and is available for your own integrations

## 🏗️ Architecture

```
Requirement
    │
    ▼
┌─────────────┐   tasks    ┌──────────────┐
│   Planner    │ ─────────▶ │  Executors   │
│    Agent     │            │   (many)     │
└─────────────┘            └──────┬───────┘
      │  monitors & retried        │  group chat / DMs
      ▼                            ▼
┌──────────────────────────────────────┐
│        MessageHub + TaskManager      │
│        SQLite Repository             │
└──────────────────────┬───────────────┘
                       ▼
              ┌────────────────┐
              │   Deliverer    │──▶ artifacts · smoke tests · READMEs
              └────────────────┘
```

The orchestrator runs a cooperative single-threaded loop with a step cap and no-progress protection — no deadlocks, no races. Every layer is swappable: polling can become event-driven, SQLite can become PostgreSQL, and the LLM client is behind a clean `LLMClient` interface.

```
hivelab/
├── app/            # Core engine
│   ├── agents/     #   Planner / Executor / Deliverer agents
│   ├── workflows/  #   Orchestrator (the collaboration loop)
│   ├── llm/        #   OpenAI-compatible client + MockLLM
│   ├── messaging/  #   Group chat & direct messages
│   ├── tasks/      #   Task lifecycle & dependencies
│   ├── storage/    #   SQLite repository
│   ├── delivery/   #   README generation & smoke tests
│   └── config/     #   Settings & persistence
├── gui/            # PySide6 desktop app (panels, theme)
└── web/            # FastAPI service backing the GUI
```

## 🚀 Getting Started

### Prerequisites

- Python **3.11+**
- (Optional) An OpenAI-compatible API endpoint for real model calls

### Installation

```bash
git clone https://github.com/WangDiwei/HiveLab.git
cd HiveLab

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Run it

**Launch the desktop app** (default when no arguments are given):

```bash
python -m hivelab
```

**Zero-config demo** — runs a full pipeline with the built-in mock LLM:

```bash
python -m hivelab --demo
```

**Submit a requirement from the command line:**

```bash
python -m hivelab "Build me a todo application"
```

**Check a project's status:**

```bash
python -m hivelab --status 1
```

**Start the Web API service:**

```bash
python -m hivelab --serve
# API docs at http://127.0.0.1:8357/docs
```

### Configure a real LLM

Copy the template and fill in your provider's details (any OpenAI-compatible endpoint works):

```bash
cp .env.example .env
```

```ini
LLM_API_BASE=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
LLM_PROVIDER=auto   # auto = real model if configured, otherwise mock
```

You can also configure everything from the GUI's **Model Settings** panel — it takes effect immediately, no restart needed.

## 🔌 REST API

The embedded service (also used by the desktop app) exposes:

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/projects` | Submit a requirement |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{id}` | Project status, tasks, agents |
| `GET` | `/api/projects/{id}/delivery` | Delivery report (poll while running) |
| `GET` | `/api/tasks` | Tasks (optionally filtered by project) |
| `GET` | `/api/agents` | All agents |
| `GET` | `/api/chats` | Group chats |
| `GET` | `/api/logs` | Recent event logs |
| `GET` | `/api/health` | Health check |

Interactive docs: `http://127.0.0.1:8357/docs` after `--serve`.

## 🗺️ Roadmap

- [ ] Event-driven agent messaging (replacing polling)
- [ ] PostgreSQL storage backend
- [ ] Parallel agent execution
- [ ] Plugin system for custom agent roles
- [ ] Streaming LLM output in the GUI

Have an idea? [Open an issue](https://github.com/WangDiwei/HiveLab/issues) — the roadmap is shaped by its users!

## 🤝 Contributing

Contributions are **welcome and encouraged**! HiveLab is young and there's plenty of room to help:

- 🐛 [Report bugs](https://github.com/WangDiwei/HiveLab/issues/new?labels=bug)
- 💡 [Suggest features](https://github.com/WangDiwei/HiveLab/issues/new?labels=enhancement)
- 📖 Improve documentation
- ⭐ Add tests, refactor, or build new agent roles

```bash
# 1. Fork & clone your fork
# 2. Create a branch
git checkout -b feat/my-feature

# 3. Make changes, then run the test suite
pytest

# 4. Open a Pull Request — thank you! 🎉
```

Small PRs are just as valuable as big ones. First-time contributors are especially welcome.

## ⭐ Star History

If HiveLab sounds interesting, a star helps others discover it!

[![Star History Chart](https://api.star-history.com/svg?repos=WangDiwei/HiveLab&type=Date)](https://star-history.com/#WangDiwei/HiveLab&Date)

## 📄 License

Distributed under the [Apache License 2.0](LICENSE).

---

<p align="center">Made with 🐝 by <a href="https://github.com/WangDiwei">WangDiwei</a> and <a href="https://github.com/WangDiwei/HiveLab/graphs/contributors">contributors</a></p>
