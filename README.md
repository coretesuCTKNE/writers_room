<div align="center">

# 🎬 GREENLIGHT — AI Screenwriter's Room

### *An Autonomous Multi-Agent Editorial Suite & Audio Table-Read Engine for Screenwriters*

[![ClickHouse Powered](https://img.shields.io/badge/ClickHouse-Sole_State_Store-FFCC00?style=for-the-badge&logo=clickhouse&logoColor=black)](#)
[![Grafana Observability](https://img.shields.io/badge/Grafana-Live_Dashboards-F46800?style=for-the-badge&logo=grafana&logoColor=white)](#)
[![Google Vertex AI](https://img.shields.io/badge/Vertex_AI-Gemini_3.6-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![Python 3.12](https://img.shields.io/badge/Python-3.12_(uv)-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)

<p align="center">
  <b>A single-process AI writer's room that converts Fountain/FDX screenplay drafts into structured story bibles, real-time analytics, automated rewrites, and multi-character audio table reads.</b>
</p>

[ 🚀 Live Demo ](https://greenlight15488.web.app/) · [ 🎥 Pitch Video ](#) · [ 📊 Grafana Telemetry ](#) · [ 📄 Architecture Docs ](#)

</div>

---

> 💡 **The Pitch:** Screenwriting requires complex continuity, subtext, and pacing that simple LLM prompts butcher. **WRITERS_ROOM** replaces fragile single-prompt generation with an orchestrated AI studio. Powered by **ClickHouse Cloud** as its sole 100% unified state store and **Grafana** for real-time agent telemetry, Greenlight gives creators Git-like screenplay versioning, automated story-bible monitoring, and live voice rehearsal capabilities.

---

## ⚡ The Partner Power-House: ClickHouse + Grafana

Greenlight rejects fragile in-memory states and slow relational databases. **ClickHouse Cloud** handles 100% of the application state, while **Grafana** provides complete observability into agent reasoning, DB query performance, and audio synthesis pipelines.

| Architecture Pillar | How Greenlight Leverages It | Impact / Advantage |
| :--- | :--- | :--- |
| **ClickHouse Cloud (Sole State Store)** | Over 20+ specialized tables manage immutable screenplay versions (`ReplacingMergeTree`), story bible facts, `agent_runs` history, scene statistics, and content-addressed TTS caches. | Zero data sprawl. Eliminates the need for separate Redis caches or secondary Postgres databases while enabling instant analytical queries over millions of script tokens. |
| **ClickHouse-Powered Agent Tools** | The **Analytics Agent** executes bound-parameter SQL directly against ClickHouse to inspect scene pacing, character line shares, and structural breakdown math. | Real-time structured analytical queries delivered instantly to the LLM without manual preprocessing. |
| **Grafana Observability Suite** | Live Grafana dashboards visualize agent execution latency, token throughput across Gemini models, ClickHouse query speed, and `tts_turn_cache` hit ratios. | Instant visibility into system bottlenecks, LLM response times, and state transitions during multi-agent orchestration. |

---

## ✨ Key Features

- **🎭 Showrunner Multi-Agent Hierarchy:** A root Coordinator agent directs specialized sub-agents (**Bible Supervisor**, **ClickHouse Analytics Agent**, and **Rewrite Specialist**).
- **🌿 Git-Style Screenplay Versioning:** Mini-Git architecture stored directly in ClickHouse (`script_versions`, `script_branches`). Branch, diff, splice scenes, and revert with full content-hash integrity.
- **🎙️ Gemini 3.1 Multi-Voice Table Reads:** Generates full multi-character audio table reads with turn-level emotion styling, or **Backing Track Mode** to let writers rehearse live with AI cast members.
- **🗣️ Live Speech Dictation:** Bidirectional WebSocket integration with **Gemini 3.5 Transcribe Live** for hands-free scene writing and real-time homophone selection.
- **🛡️ Deterministic Safety Guardrails:** Strict SQL regex wall blocks schema exfiltration; programmatic verifiers enforce script formatting before agents commit changes.

---

## 🏗️ Architecture & Data Pipeline

┌────────────────────────────────┐
                                  │   📊 Grafana Dashboards        │
                                  │ (System & Agent Observability) │
                                  └───────────────▲────────────────┘
                                                  │ Telemetry
┌─────────────────────────┐          ┌────────────────┴────────────────┐
│   👤 Writer (React SPA) ├─────────►│    🚀 FastAPI Backend Engine    │
└─────────────────────────┘ REST/WS  └───────┬─────────────────┬───────┘
│                 │
Agent Calls (ADK) │                 │ SQL Queries / Reads
▼                 ▼
┌───────────────────────┐   ┌───────────────────┐
│  🤖 Vertex AI         │   │ ⚡ ClickHouse      │
│  (Gemini 3.6 / Live)  │   │   (Sole Store)    │
└───────────────────────┘   └───────────────────┘


---

## 🛠️ ClickHouse Schema Architecture

Greenlight stores all immutable operational data and vector-like script context inside ClickHouse:

ClickHouse Cloud State Store
├── 📜 Version Control   ► scripts, script_versions, script_branches
├── 🎭 Screenplay Structure ► scenes, characters, bible_facts, scene_stats
├── 🔊 Audio Engine      ► table_read_takes, tts_turn_cache, voice_casting
└── 🤖 Agent Operations  ► agent_runs, script_access, active_sessions


---

## 🚀 Quick Start

### 1️⃣ Prerequisites
- **Python 3.12+** (managed via `uv`)
- **ClickHouse Cloud** instance (or local ClickHouse binary)
- **Google Cloud Vertex AI** credentials

### 2️⃣ Environment Configuration
Create a `.env` file in the root directory:
```env
CLICKHOUSE_URL=[https://your-clickhouse-instance.clickhouse.cloud:8443](https://your-clickhouse-instance.clickhouse.cloud:8443)
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_secure_password

GOOGLE_CLOUD_PROJECT=your_gcp_project_id
GOOGLE_CLOUD_REGION=us-central1
3️⃣ Installation & Boot
Bash
# Clone the repository
git clone [https://github.com/coretesuCTKNE/writers_room.git](https://github.com/coretesuCTKNE/writers_room.git)
cd writers_room

# Set up environment with uv
uv venv
source .venv/bin/activate
uv pip install -e .

# Run database migrations / schema verification
python -m greenlight.db.init_db

# Start Greenlight Single-Process Engine
./start.sh

```
---

# Further Reading

- [ARCHITECTURE.md](./ARCHITECTURE.md) — deep dive: frameworks, data flow, agents, audio pipeline, deployment & safety

## License

[Apache License 2.0](./LICENSE)