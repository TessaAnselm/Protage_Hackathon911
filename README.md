# MigrationOps

Secure, self-improving migration pipeline: upload a vendor file, profile and secure it,
recall prior mappings, generate new field mappings with human approval, migrate + reconcile,
then learn from the outcome. A monster mascot on the frontend "eats" each record as it's
processed and sorts it into the modern DB or quarantine.

## Demo Video

[Watch the demo video](https://drive.google.com/file/d/1vcnI7dyBww6r1zEI4ye3SYwGKgBUZ578/view?usp=sharing)

## Run it

```
conda run -n hack uvicorn backend.main:app --reload --app-dir . --port 8000
```

Then open http://localhost:8000

## Sponsor tool integration status

| Tool | Status | Notes |
|---|---|---|
| Cognee | **Live** | `backend/adapters/cognee_adapter.py` — stores/recalls mapping memory |
| OpenAI (LLM_API_KEY) | **Live** | `backend/adapters/llm_adapter.py` — generates field mapping suggestions |
| HotData | **Live** | `backend/adapters/hotdata_adapter.py` — real SQL profiling via the `hotdata-framework` SDK, run as one query over an inline `VALUES` table in a managed database |
| HydraDB | **Live** | `backend/adapters/hydra_adapter.py` — real ingest/semantic-search via the `hydra_db` SDK; mapping recall depends on HydraDB's own async indexing, so a just-saved mapping may take a little while to become recallable |
| Snyk | **Live** (CLI) | `backend/adapters/snyk_adapter.py` — run separately/locally (`snyk test`, or `GET /api/security-scan`); intentionally not exposed in the web UI |
| RocketRide | **Live** | `backend/adapters/rocketride_adapter.py` — key authenticates against `https://staging.rocketride.ai/`, a staging endpoint given directly by the sponsor (not in RocketRide's own docs, which only mention the default `https://cloud.rocketride.ai/` — that one rejects this key). Actually orchestrating: `/api/ask` ("Ask about this migration") builds a real RocketRide pipeline (`chat` source → `llm_openai` → `response`, per their documented `.pipe` schema), starts it with `client.use()`, and answers via `client.chat()` — the LLM call is made *by the RocketRide-hosted node*, not by us directly |
| Modiqo Rote | **Live** | `backend/adapters/modiqo_adapter.py` — "Modiqo Rote" is the `rote` CLI itself, already installed and authenticated on this machine (`rote whoami`). Its own play system is built for an agent to crystallize interactive sessions, not for a backend to call per-request, so mapping capture/replay stays app-owned state (`backend/data/plays.json`) while connection identity is genuinely delegated to Rote |

All 7 sponsor tools are now live. Each adapter still exposes the same function
signature regardless — that's what made swapping RocketRide/HydraDB/HotData/Modiqo
from local fallback to real integrations a same-file change, no callers touched.
