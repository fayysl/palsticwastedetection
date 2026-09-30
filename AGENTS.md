# AGENTS.md — EcoScan

Guidance for AI coding agents (Claude Code, Cursor, Copilot, Codex…) working in this repo.
Read this first. For the *why* behind the product, see `docs/PRD.md`. For architecture, see
`docs/TECHNICAL_DESIGN.md`. For data and privacy rules, see `docs/DATA_GOVERNANCE.md`.

## What this project is

EcoScan is a Flask web app that detects plastic waste in photos using a free OpenRouter vision
model, then tells the user how to segregate, recycle or dispose of each item and tracks their impact.
Flow: **Detect → Understand → Act → Track**.

## Tech stack (do not change without updating the design doc)

- **Backend:** Python 3.11, Flask 3, gunicorn. No other web framework.
- **Frontend:** server-rendered Jinja templates + plain HTML/CSS/JavaScript. **No React, no build
  step, no npm at runtime.** Chart.js is vendored at `static/vendor/chart.umd.min.js`.
- **AI:** OpenRouter Chat Completions API, free vision models only, called with `requests`.
- **DB:** Supabase Postgres through its REST API (PostgREST) with `requests`, with a SQLite fallback. **Do
  not add `supabase-py`** or an ORM.
- **Deploy:** Render (`render.yaml`). Tests: pytest.

## Project structure

```
app.py                  create_app(): page routes + JSON API. Keep routes thin.
services/ai.py          Image prep (resize, EXIF strip, thumbnail), model selection, OpenRouter call, JSON parsing
services/knowledge.py   Deterministic rules: categories, resin codes, bins, actions, CO2, points, levels
services/store.py       SQLiteStore / SupabaseStore (same interface) + summarize() for dashboards
templates/              base.html layout; index, scan, dashboard, guide, scan_detail pages
static/css/style.css    All styles. CSS variables on :root, dark mode via prefers-color-scheme
static/js/common.js     api() fetch wrapper (adds X-Client-Id), esc() HTML escaping, getClientId()
static/js/scan.js       Upload UI + renderResult(scan) (also reused by scan_detail.html)
static/js/dashboard.js  KPIs, charts, history list
supabase/schema.sql     The only DB schema. Keep in sync with store.COLUMNS
tests/test_app.py       pytest suite (AI and network are always mocked)
```

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python app.py              # dev server on :5000 (demo mode if OPENROUTER_API_KEY unset)
pytest -q                  # must pass before every commit
gunicorn app:app           # production-like run
```

## Core design rules (the "why")

1. **The AI detects; the knowledge base decides.** The model only returns
   `{items:[{name, category, resin_code, count, confidence, condition}], summary, tips}`.
   All bins, actions, CO₂ and points come from `services/knowledge.py`. Never let model text choose
   the bin or actions. This keeps advice consistent across the free models.
2. **Treat model output as untrusted.** `knowledge.enrich()` clamps counts (1–500) and confidence (0–1),
   maps unknown categories to `other` and invalid resins to the category default, and truncates strings.
   Keep that defensive style for any new field.
3. **Free models fail, so always have a fallback.** `ai.detect()` tries models in order
   (`OPENROUTER_MODEL` → auto-discovered free image models → `FALLBACK_MODELS`) and moves on after HTTP errors,
   API errors or unparseable JSON. It stops early on 401/402. Never hard-code a single model.
4. **Storage backends are interchangeable.** Anything added to one store must be added to the other, to
   `COLUMNS`, and to `supabase/schema.sql`.
5. **Scan results beat persistence.** If saving fails, still return the analysis with `save_error`.
6. **Privacy by default.** Never store the full-size upload, EXIF data, IP addresses or names. The Supabase
   `service_role` key is server-only. Never send it or any secret to the browser.

## Coding conventions

- **Python:** PEP 8, 4-space indent, ~110-char lines, module docstrings explaining purpose. Small pure
  functions in `services/`. Configuration comes only from env vars (`os.getenv`), loaded by `python-dotenv` locally.
- **API errors** return JSON `{"error": "<human-readable message>"}` with a real status code
  (400 bad input, 413 too large, 502 AI failed, 503 storage unavailable).
- **JavaScript:** vanilla ES2020, no frameworks. Always use `api()` for requests. **Escape every
  model- or user-derived string with `esc()`** before putting it in `innerHTML`.
- **CSS:** reuse existing tokens (`--primary`, `--surface`, `--border`…) and components (`.card`, `.btn`,
  `.tag`, `.bin-tag`). Layouts must work at 390 px width with no horizontal scroll.
- **Templates:** extend `base.html`, set `page` for nav highlighting, put page scripts in `{% block scripts %}`.
- **Tests** never call real OpenRouter or Supabase. Monkeypatch `ai.detect`, `requests.post` or `requests.request`.

## Decision trees

**Adding a new plastic category (e.g. "blister pack")**
1. Add an entry to `CATEGORIES` in `services/knowledge.py` (label, icon, default_resin, avg_weight_g, bin,
   segregation, actions, reuse).
2. Add its key to `CATEGORY_KEYS` in `services/ai.py`, so the prompt lists it.
3. Add any special bin rules in `enrich()`, with a test in `tests/test_app.py`.
4. The guide page and charts pick it up automatically.

**Changing what the AI returns**
- Update `PROMPT` in `services/ai.py`, then make `enrich()` read the new field defensively,
  then update `DEMO_DETECTION`, then add a test. Update the prompt contract in `docs/TECHNICAL_DESIGN.md`.

**Adding a stored field**
- Add it to `store.COLUMNS` and `_row()`, the SQLite `CREATE TABLE`, and `supabase/schema.sql` (with an
  `alter table … add column if not exists` note for existing deployments).

**Adding an API endpoint**
- Add it inside `create_app()` in `app.py`, keep the logic in `services/`, return JSON errors, identify
  visitors with `client_id()` (never trust other headers), then add a test and document it in the README API table.

**A scan fails in production**
- Check the Render logs for `OpenRouter <model> -> <status>`. A 429 means rate-limited (set
  `OPENROUTER_MODEL` to a list). A 401 means a bad key. A 404 means the model was removed (auto-discovery handles this).

## Don'ts

- Don't add user accounts, a SPA framework or a bundler (out of scope, see PRD §4.2).
- Don't use paid models or make paid-model IDs the default.
- Don't log image bytes, full model responses containing user photos, or secrets.
- Don't commit `.env`, `instance/` or `*.db`.
- Don't skip or delete tests to get green.
