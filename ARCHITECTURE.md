# Greenlight Architecture

Technical architecture of **Greenlight — AI Screenwriter's Room**: a single-process FastAPI backend, a static React frontend, ClickHouse as the sole state store, and Google Vertex AI (Gemini) as the model layer.

All paths are relative to `src/greenlight/` unless noted.

---

## 1. Core frameworks and environment

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.12, `uv`-managed | `pyproject.toml`, lockfile committed |
| API framework | FastAPI + Starlette | single process, mounts 12 routers + 2 WebSocket handlers (`api/app.py:52-64`) |
| Agent framework | Google ADK (`google-adk`) | `LlmAgent` definitions in `agents/`, `Runner` driven by `api/services/agent_runner.py` |
| LLM SDK | `google-genai` (Vertex mode) | one shared factory: `utils/genai_client.py` |
| Database | ClickHouse (`clickhouse-connect`) | 20+ tables, `db/schema.sql` |
| Frontend | Vite + React + Emotion + Zustand | `web/src/` |
| Audio | pydub (stitch), wave (PCM→WAV), wavesurfer.js (playback) | `tools/stitcher.py`, `web/src/pages/TableReadPage.tsx` |
| Auth | Firebase Anonymous (`firebase-admin`) | `api/auth.py` |
| Storage | local disk (dev) or Cloud Storage (prod) | `tools/audio_store.py` |

**Configuration** (`config.py`): a single pydantic-settings `Settings` singleton. Every model id (`agent_model=gemini-3.6-flash`, `tts_model=gemini-3.1-flash-tts-preview`, `coverage_model`, `dictation_model`), region, and path knob lives there. `validate_runtime()` runs at startup and surfaces fatal-adjacent misconfigurations (missing Vertex project, unset ClickHouse URL) as logged warnings; LLM-dependent routes self-degrade to 503.

**Runtime guards**: the app refuses non-loopback bindings in dev posture (`app.py:73-80` warns when `API_HOST` is exposed), and the `/generated_audio` static mount is only created when auth is **off** — in auth mode audio is served from GCS public URLs so nothing bypasses the middleware (`app.py:99-117`).

---

## 2. Action mechanisms and data connectivity

**Request path.** Every HTTP call flows: client → `FirebaseAuthMiddleware` (pure ASGI, sets a `principal` contextvar) → CORS → route → service/tool layer → ClickHouse. Auth-off mode (dev/tests) short-circuits to principal `"local"`.

**DB layer** (`db/client.py`): a `get_ch_client()` singleton plus four primitives — `query()`, `insert()`, `command()`, `ping()`. All state is in ClickHouse; there is no second database, no cache server. Key tables:

- `scripts`, `script_versions`, `script_branches` — immutable version graph (ReplacingMergeTree)
- `scenes`, `characters`, `bible_facts`, `scene_stats` — parsed screenplay structure
- `coverage`, `notes` — reader verdicts and per-note spans
- `table_read_takes`, `tts_turn_cache`, `voice_casting`, `generated_audio_assets` — audio pipeline
- `agent_runs` — every agent execution persisted with prompt, result, elapsed time
- `script_access`, `active_sessions`, `dictation_sessions` — ownership and session state

**The ClickHouse integration — why this database, and how it's used:**

- **Single-writer discipline.** Every write goes through `db/client.py` `insert()`/`command()`; every read through `query()`. Connection is env-driven (`CLICKHOUSE_URL`/`USER`/`PASSWORD`) so the same code runs against a local binary (dev/tests) or ClickHouse Cloud (prod) with zero code forks. All SQL uses `%(name)s` parameter binding — no string-built queries anywhere.
- **ClickHouse idioms, not relational habits.** Upsert-style tables (`script_branches` head pointer, `script_versions`, `active_sessions`, `writing_goals`, `dictation_sessions`) use `ReplacingMergeTree` — newest row wins on `FINAL`, no UPDATEs. Immutable version history, TTS cache rows, and agent runs are plain `MergeTree` ordered by time for cheap append/scan. Schema is idempotent DDL (`db/schema.sql`) + `ALTER ... ADD COLUMN IF NOT EXISTS` migrations for older databases, applied by `db/seed/apply_schema.py`.
- **It's the analytics backbone, not just persistence.** Columnar aggregation powers the story-ops analytics: `countIf` verdict breakdowns, `UNION ALL` goal-vs-wordcount queries, `FINAL` joins over `scene_stats` for pacing/scene composition. Per-version word/page counts live in `script_versions` so progress queries are a single indexed read.
- **Agents operate it safely.** The analytics agent reaches the DB through a read-only `SELECT`-only tool (`agents/tools.py:31-40` regex wall forbids writes, `system.*`/`information_schema`, and file/URL/remote table functions). Every agent run is itself persisted to `agent_runs` — the tool stores the audit log in the same system it reads.
- **Observability shares the store.** ClickHouse doubles as Grafana's datasource: the Story Ops coach runs `grafana_query_clickhouse` against the production DB through the Grafana ClickHouse datasource, so the room's live state and its observability charts read from the same tables.

**Data connectivity details:**

- TTS turn results are **content-addressed** — `turn_hash(text, voice, style_tags)` keys `tts_turn_cache`, so re-running a table read skips any identical turn (`tools/tts_engine.py:70-77`).
- The analytics agent's SQL tool is **bound-parameter only**; write keywords, schema exfiltration, and file/URL table functions are regex-blocked (`agents/tools.py:31-40`).
- Audio URLs are dual-shaped (`/generated_audio/<name>` locally, `https://storage.googleapis.com/...` in prod) and `audio_store.py` is the single owner of both shapes — every consumer (`tts_engine`, `stitcher`, routes) goes through `store_audio`/`load_audio_bytes`.

**Frontend connectivity:** REST for CRUD, one WebSocket (`/api/ws/agents`) fed by an in-process pub/sub broker with bounded queues and slow-subscriber drop (`api/services/agent_runner.py:77-108`), and a second WebSocket (`/api/ws/dictation`) for streaming speech. The frontend WS hook uses exponential backoff (`web/src/lib/useAgentWebSocket.ts`).

---

## 3. Script processing and document grounding

**Ingestion** (`api/routes/scripts.py`): upload accepts Fountain and Final Draft (`.fdx`) — FDX is converted via `tools/fdx_to_fountain.py`, then Fountain text goes through `fountain_normalizer.py` before persistence. Creating a script from scratch uses `tools/screenplay_template.py` (title-page skeleton + starter scenes).

**Fountain parsing** — regex lives in one module only (`tools/_fountain_common.py`: scene headings, character cues, parentheticals, boneyard). Two parsers sit on top:

- `tools/fountain_document.py` — full-document parse into typed `ScriptElement`s (title page, headings, action, dialogue, dual dialogue), with `render_document()` for lossless round-trips.
- `tools/fountain_parser.py` — scene-level parse into `DialogueTurn`s (speaker, text, `Parenthetical` with style tags like `[whispers]`, `[angry]`), plus action-line pacing math (`calculate_gap_ms`) used for stitching.

**Grounding — the script repo** (`api/services/script_repo/`): the screenplay is modeled like a mini-Git:

- Every edit commits an **immutable version** (`script_versions`): full `raw_fountain`, `content_hash`, word/page counts, parent link.
- **Branches** (`script_branches`) carry a moving `head_version_id`; `commit_version` advances the head, `revert_version` creates a *new* version that restores an ancestor, `apply_branch` merges one branch's head into another after `preview_apply`/`diff_versions` (element-level diff in `script_repo/parsing.py`).
- A `main` branch with a root snapshot is scaffolded on script creation (`script_repo/state.py`).
- After every commit, `persist_breakdown()` re-parses the version and upserts `scenes` (heading, page, cast, locations, props, setting, time-of-day), `characters`, and `scene_stats` — this is what grounds the agents: analytics and bible tools read these tables, never raw text guesswork.

**Editor surface**: the React `SceneEditor`/`FountainPreview` operate per scene; `replace_scene()` splices a scene by ordinal and re-renders the document before the next version commit.

---

## 4. Audio and speech generation

**Voice casting** (`tools/voice_casting.py`): 13 prebuilt Gemini voices with style metadata; deterministic assignment round-robins `DEFAULT_VOICES` across the scene's cast (user preferences override). Assignments persist in `voice_casting` per script.

**Synthesis** (`tools/tts_engine.py`):

- Per turn: style tags from the parenthetical are converted into a natural-language style prompt ("Say in an angry, furious tone: ...").
- Gemini 3.1 Flash TTS returns raw PCM at 24 kHz, wrapped to WAV (`_pcm_to_wav`).
- Concurrency is capped by a `asyncio.Semaphore(5)`; each call has a configurable deadline (`tts_call_timeout_seconds`).
- Turn cache (`tts_turn_cache`) makes iterative table reads cheap — same text + voice + tags = instant reuse.

**Stitching** (`tools/stitcher.py`): pydub concatenates turn audio with computed silences between turns (pacing derived from the following action line), pads 500 ms head / 1 s tail, and exports a 24 kHz WAV. Two modes: full table read, and **backing track** where the user's character is replaced by silence so they can perform their line over the AI cast.

**Streaming speech (dictation)** (`api/ws/dictation.py`): bidirectional WebSocket proxy to **Gemini 3.5 Transcribe Live** (Live API). Client audio → Gemini, Gemini text → client with dedup; VAD silence/padding thresholds and 10-minute session caps are configurable. Held-key shortlist (keys 1–9) lets the writer pick between near-homophones during capture.

**Storage**: `tools/audio_store.py` switches between local disk (dev) and Cloud Storage (prod: upload → public object URL → serve, with deletes restricted to the configured bucket).

---

## 5. Partner integration and infrastructure

| Google Cloud service | Role | Code entry |
|----------------------|------|-----------|
| **Vertex AI — Gemini 3.6 Flash** | agents, coverage reader | `utils/genai_client.py`, `coverage_service.py` |
| **Vertex AI — Gemini 3.1 Flash TTS** | multi-character speech | `tools/tts_engine.py` |
| **Gemini Live API** | rehearsal conversation + dictation | `api/ws/dictation.py`, agent sessions |
| **ADK** | agent framework | `agents/`, `agent_runner.py` |
| **ClickHouse Cloud** | all application state | `db/client.py` |
| **Cloud Storage** | audio assets (prod) | `tools/audio_store.py` |
| **Cloud Run** | API + SPA hosting (prod) | `scripts/redeploy.sh` (dev repo) |
| **Firebase Hosting + Anonymous Auth** | static site + per-visitor identity | `api/auth.py`, `web/src/lib/firebase.ts` |

**LLM client discipline** (`utils/genai_client.py`): `genai.Client` is constructed **only** here — thread-safe lazy factory, keyed by `(purpose, location)` so TTS (`us-central1` regional preview) and dictation (`global`) maintain separate clients. Vertex credentials resolve through service account / gcloud ADC / Cloud Run metadata server (`has_vertex_credentials()`).

**Deployment topologies**: identical code, two postures. Dev: loopback-only, auth off, local ClickHouse binary, audio on disk, `./start.sh` boots everything. Prod: `FIREBASE_PROJECT_ID` set (auth on, owner-scoped rows), `GCS_BUCKET` set (audio to GCS), ClickHouse Cloud endpoint — flipped purely by environment variables, no code forks.

---

## 6. Reasoning, state and logic hosting

**State**: 100% in ClickHouse. The app process is stateless besides in-memory agent Runners and the event broker — it can restart without losing scripts, versions, coverage, takes, or caches. Session continuity ("which script/branch/version is this user editing") lives in `active_sessions`, keyed by principal.

**Deterministic logic vs. LLM reasoning** — the split is deliberate:

| Deterministic (pure code) | LLM reasoning |
|---|---|
| Fountain parsing/round-trip | Coverage verdict + notes |
| Scene splice, diff, revert | Rewrite passes |
| Voice casting round-robin | Showrunner routing decisions |
| Turn hashing, cache lookup | Bible fact extraction/verification |
| Silence-gap math, stitching | Rehearsal conversation (Live API) |
| Bible-monitor rule checks | Canon judgment |

**Reasoning hosting**: agent reasoning happens in Vertex-hosted Gemini models via ADK `Runner`s (memoized per agent — kills the 5–10 s cold start, `agent_runner.py:115-131`). Every run is logged to `agent_runs` (agent, prompt, result JSON, elapsed, status). Rule-based canon enforcement (e.g., "only child" contradictions) is a deterministic pre-check in `tools/bible_monitor.py` that runs alongside the LLM bible agent.

---

## 7. How agents are handled

**Topology** (`agents/showrunner.py`): a root `LlmAgent` (`showrunner`) with three sub-agents —

- **bible** — continuity supervisor: verifies scripts against the story bible, extracts new facts (read/write `bible_facts`)
- **analytics** — data analyst: answers real questions from ClickHouse (read-only SQL tool)
- **rewrite** — rewrite specialist: reads latest coverage + notes, produces targeted scene passes

The showrunner routes by intent, transfers to exactly one specialist per step, and threads `script_id` through every hop so tools target the right rows. Coverage is intentionally *not* an agent — it's a structured-JSON service call (`coverage_service.py`) for reliable schemas.

**Execution** (`api/services/agent_runner.py`):

1. `run_agent(agent_name, prompt, script_id, scene_id)` — validated against the registry.
2. Context block injected into the prompt (script title + ids + tool-usage instructions).
3. Memoized ADK `Runner` (per-agent `InMemorySessionService`) streams events; the final text part is captured.
4. Every event of the run publishes an `AgentEvent` (`running` → `completed`/`error`) to the **AgentBroker**.
5. `/api/ws/agents` fans the broker's events out to all connected browser clients — the UI shows live agent status.
6. The run is persisted to `agent_runs` regardless of outcome.

**Other agent surfaces**: `routes/agent_work.py` (agent job endpoints), `routes/history.py` (agent_runs feed), and the AgentsPage console in the frontend.

---

## 8. Agent tools and function calling

Agent tools are **plain Python functions** wrapped in ADK `FunctionTool`s — built lazily and cached per agent (`agents/tools.py:313-352`). No prompt-side JSON schema handoff: ADK introspects the function signatures.

| Agent | Tools | Writes? |
|-------|-------|---------|
| bible | `list_bible_facts`, `add_bible_fact`, `delete_bible_fact`, `list_characters`, `list_scenes`, `get_coverage`, `get_coverage_notes` | yes (facts only) |
| analytics | `query_clickhouse`, `script_stats`, `coverage_history`, `list_scenes` | no |
| rewrite | `get_coverage`, `get_coverage_notes`, `list_scenes` | no |

**Safety rails on function calling:**

- All tools go through parameterized ClickHouse queries — no string-built SQL.
- `query_clickhouse` accepts only `SELECT` (anchored regex), rejects writes, `system.*`/`information_schema`, and file/URL/remote table functions (`agents/tools.py:31-40`).
- `add_bible_fact` validates category against a fixed enum and rejects empty claims.
- Tool results are JSON-normalized (datetimes → ISO strings) before ADK serialization (`agents/tools.py:166-177`).
- Non-deterministic tool exceptions are caught and returned as `{"error": ...}` dicts so the agent can reason about failure instead of crashing the run.

---

## 9. Deployment and safety

**Deploy (production):** Cloud Run (FastAPI, public route), Firebase Hosting (static React), ClickHouse Cloud, Cloud Storage `greenlight-audio`. Everything deploys from local tooling (`gcloud`/`firebase` CLIs) — GitHub is not in the deploy path. Configuration is env-var driven on the Cloud Run template; secrets (ClickHouse password) come from Secret Manager bindings.

**Safety design:**

- **Auth**: Firebase ID-token verification on every `/api/*` request (Bearer header for REST, `?token=` for WebSocket upgrades since browsers can't set WS headers); each visitor's scripts are owner-scoped by `principal`. `/api/health` is the only exempt path.
- **Static mount bypass**: audio static mount is compiled out in auth mode (§1); in prod, audio is served by public GCS object URLs so unauthenticated paths never touch user data.
- **SSRF/SQL safety**: parameterized SQL everywhere; the analytics tool's allow/deny regex wall (§8); GCS deletes restricted to URLs matching the configured bucket (`audio_store.py:80-89`).
- **Degraded mode**: with no LLM credentials the API still boots — coverage/table-read/rewrite return 503 with hints, and `validate_runtime()` logs exactly what's missing.
- **Resource caps**: bounded event queues (drop-on-full), TTS semaphore + per-call timeout, table-read turn limit, take retention limit, dictation session caps — all tunable in `config.py`.
- **Local posture**: dev binds loopback only, auth off, and warns loudly on any non-loopback bind.

---

## Further reading

- [README.md](./README.md) — product overview + quick start
- `db/schema.sql` — full table definitions
- `api/routes/` — one router per resource, the best map of behaviors
