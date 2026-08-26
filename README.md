# NavyBI Prototype

A self-contained conversational analytics prototype for post-mission reporting data, originally built as a 24-hour sprint and iterated since. See [PLAN.md](PLAN.md) for current status, open items, and the full decision/build history; [GOVERNANCE_NOTES.md](GOVERNANCE_NOTES.md) for the DoW ethical-principles self-assessment; [QUESTION_TEST_LOG.md](QUESTION_TEST_LOG.md) for an honest, multi-round accuracy report on the conversational layer; [rmf/](rmf/) for the RMF documentation package; and [POWERBI_MIGRATION.md](POWERBI_MIGRATION.md) for how to move the dashboard layer to Power BI when ready.

## What this is

An end-to-end pipeline — synthetic messy source data (in three different formats/ingestion paths: CSV, JSON, and an actual SQLite database, simulating three different systems) → automated, logged cleansing → a governed semantic layer (DuckDB) → a FastAPI backend → interactive dashboards and a plain-language query interface (a React/TypeScript frontend) — all behind real (if minimal) multi-user login and role-based access — all built in code so every step is inspectable.

## What this is NOT

- **Not connected to real data.** All data is fabricated (`data/generate_synthetic_data.py`) — no real unit, personnel, mission, training/certification, or maintenance information.
- **Not DoD-grade identity management.** Login is real (see below), but uses local demo accounts, not DoD PKI/CAC or an enterprise identity provider — see [rmf/SSP.md](rmf/SSP.md)'s IA control section.
- **Not RMF-assessed or ATO'd.** A full RMF documentation package exists (see below), but it's a developer self-assessment, not an independent assessment, and no Authority to Operate has been requested or granted — an ATO is an Authorizing Official's decision, not something this repository can produce on its own. See [rmf/POAM.md](rmf/POAM.md).
- **Not verified against a real Power BI instance.** The export/DAX work is architecturally ready (see below) but Power BI Desktop is Windows-only and this was built on a Mac — untested against the real thing.

## Multi-user auth and the RMF package

Real login and two roles (admin, analyst) — see `auth/` (bcrypt-hashed credential store, framework-agnostic) and `api/deps.py`/`api/routers/auth.py` (a signed JWT in an httpOnly cookie, issued by the FastAPI backend on login). Demo credentials are seeded by `auth/seed_users.py` (run it once before first use); an admin sees the governance panel and an audit log of every conversational query ever asked (who, when, what, which interpreter answered), an analyst sees the dashboards and conversational layer only. This closes the audit-logging gap `GOVERNANCE_NOTES.md` names explicitly.

A full RMF documentation package lives in [rmf/](rmf/): a FIPS 199 system categorization (both as-built and target), a System Security Plan with control status grounded in actual code references, a Security Assessment Plan and preliminary self-assessment report, and a POA&M with a named path to an actual ATO decision. Read [rmf/POAM.md](rmf/POAM.md) first — it states plainly what would still need to happen (an independent assessment, a real Authorizing Official) before any of this could support a real deployment.

## Conversational layer: real LLM, with a fallback

The "ask a question" feature is backed by a real LLM — OpenRouter, model `google/gemma-4-31b-it:free` (switched from `nvidia/nemotron-3-ultra-550b-a55b:free` in round 7 for speed and rate-limiting reasons — see QUESTION_TEST_LOG.md) — via `app/llm_interpret.py`, with the original keyword/entity matcher (`app/nl_query.py`) demoted to an automatic fallback for when the LLM is unconfigured, errors, times out, or gets rate-limited (a real risk on a free model — observed directly during testing). Every answer in the app states which interpreter actually produced it, including when a keyword-based sanity check overrides the LLM's own classification (see round 7).

To enable it, create a `.env` file in the repo root (gitignored, never committed) with:
```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemma-4-31b-it:free
```
Without a `.env` file, the app runs exactly as it did through round 5 — keyword matcher only. Swapping `OPENROUTER_MODEL` to a different model is supported architecturally, but per round 7, treat it as a real change requiring the full test suite to be re-run, not a safe drop-in swap — a different model can have different classification biases that reopen failure modes earlier rounds closed.

## Running it

The easy way — one script does setup (idempotent, skips what's already done) and starts the app:
```bash
./run.sh          # development: API on :8000, Vite dev server on :5173 (open this one)
./run.sh --prod   # production-style: build the SPA and serve everything from :8000
./run.sh --reset  # wipe and regenerate synthetic data, warehouse, and users first
./stop.sh         # stop whatever's running on :8000 / :5173
```

In `--prod` mode the FastAPI process serves the built frontend itself, so there's one process, one port, and no CORS. Set `JWT_SECRET` in `.env` if you want sessions to survive a restart (without it, a random per-process secret is generated — no default secret ships in this repo).

Docker is also wired up, though **unverified** — Docker isn't installed on the machine this was built on:
```bash
docker compose up --build   # then open http://localhost:8000
```

Or by hand:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 data/generate_synthetic_data.py
python3 pipeline/clean.py
python3 warehouse/semantic_layer.py
python3 auth/seed_users.py
uvicorn api.main:app --reload --port 8000 &
cd frontend && npm install && npm run dev
```

Then open `http://localhost:5173` and log in with one of the demo accounts `auth/seed_users.py` prints to the console. The Vite dev server proxies `/api` to the FastAPI backend on port 8000, so the browser only ever talks to one origin.

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/test_api.py           # 44 API tests: auth, RBAC, response contracts
python3 -m pytest tests/test_static_serving.py # production static-serving (skips if frontend/dist isn't built)
python3 tests/test_questions.py               # NL interpretation suite -- hits the real LLM, see QUESTION_TEST_LOG.md

cd frontend && npm test                        # 33 component/logic tests
cd frontend && npm run typecheck && npm run lint && npm run build
```

The API tests run against the real warehouse and real seeded accounts rather than mocks — the point of that layer is the wiring between auth, roles, and the semantic layer, and mocked internals would pass while that wiring is broken. They force the deterministic keyword interpreter so they don't depend on the LLM being reachable or in-quota. [CI](.github/workflows/ci.yml) runs all of this on push (pytest on a Python 3.9/3.11 matrix, plus the frontend checks).

## Structure

```
data/generate_synthetic_data.py   Fabricated post-mission dataset (CSV + JSON + SQLite sources) with intentional messiness
pipeline/clean.py                 Automated cleansing with a logged, auditable decision trail
warehouse/measures.sql            Semantic-layer views: relationships + named, documented measures
warehouse/semantic_layer.py       Builds the DuckDB warehouse; MEASURE_DOCS holds SQL + DAX per measure
warehouse/export_for_powerbi.py   Exports cleaned tables to Parquet for Power BI import
warehouse/generate_powerbi_measures_doc.py  Generates POWERBI_MEASURES.md from MEASURE_DOCS (don't hand-edit that file)
app/nl_query.py                   Conversational layer: question -> intent -> SQL -> chart spec + explanation
app/llm_interpret.py              Real LLM interpretation via OpenRouter; the primary path when configured
auth/seed_users.py                 Seeds demo user accounts (run once before first use)
auth/auth.py                       Credential verification, role checks, and query audit logging (framework-agnostic)
api/main.py                       FastAPI app: CORS, router wiring, health check
api/deps.py                       JWT-cookie session handling (login/current-user/admin-only dependencies)
api/routers/                      auth, dashboard (Overview/Trends/Map/Drill-down data), ask, governance, audit-log endpoints
frontend/                         React + TypeScript + Tailwind SPA -- sidebar nav, dashboards (Recharts), map (react-leaflet), conversational query UI
rmf/                               RMF documentation package (categorization, SSP, SAP, SAR, POA&M)
tests/test_api.py                 API tests: auth, role-based access control, response contracts
tests/test_static_serving.py      Production-mode tests: SPA serving and client-side route fallback
tests/test_questions.py           Curated realistic-question test harness (see QUESTION_TEST_LOG.md)
Dockerfile, docker-compose.yml    Container packaging (written, not yet verified -- no Docker on the build machine)
run.sh / stop.sh                  Start (dev or --prod) and stop the app
```

## What was actually demonstrated

- A real, working conversational-BI architecture, not just a mockup — every "Ask a question" answer shows its generated SQL, the plain-language measure definition, and a link to manually verify the underlying rows.
- Automated data cleansing that is auditable rather than silent (duplicate removal, invalid-value flagging, format normalization — all logged with counts and reasons), applied consistently across three genuinely different source formats and ingestion paths: CSV, JSON, and an actual SQL database (SQLite, via a real `sqlite3` connection).
- A governed semantic layer that includes a two-hop relationship (training records → personnel → units) and a conformed dimension shared across two independently-generated sources (equipment_type, used by both readiness and maintenance), not just flat direct foreign keys — plus DAX equivalents generated for every measure so a future Power BI report computes the same numbers.
- A measured, honestly-reported accuracy result for the conversational layer, tracked across five rounds of keyword-matcher fixes (6/15 → 8/15 → 10/15 → 13/19 → 15/25 fully correct), then a real LLM integration in round 6, then a model swap in round 7 — including a pattern that held across every round: adding real surface area (a phrasing edge case, a new data source, deliberate adversarial probing, a second interpreter, or a different model behind that interpreter) kept finding a genuine bug — an actual crash and a documented design tradeoff in round 6; the exact "confident wrong-domain answer, no caveat" failure mode reopened by a different model's bias in round 7, plus a new caveat category for ranking questions a time-series chart can't actually answer. See QUESTION_TEST_LOG.md for the full story across all seven rounds.
