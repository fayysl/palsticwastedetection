# ♻️ EcoScan — Intelligent Plastic Waste Detection and Environmental Action System

An AI-based system that **detects plastic waste from images**, identifies the **type and level** of waste,
and provides **environmental actions** such as segregation, recycling or disposal recommendations.

**Concept: Detect → Understand → Act → Track**

| Step | What happens |
|------|--------------|
| 🔍 **Detect** | User clicks **Scan Waste**, uploads or takes a photo. An AI vision model (free, via OpenRouter) finds plastic bottles, bags, food containers, packaging, cups, straws/cutlery and jugs. |
| 🧠 **Understand** | Each item is mapped to its resin code (#1 PET … #7 Other), recyclability, bin type and a waste level (none / low / medium / high). |
| ♻️ **Act** | Step-by-step segregation, recycling, reuse and disposal guidance per item, AI tips for that photo, and a "find recycling centres near me" link. |
| 📊 **Track** | A dashboard with scan history, eco points and levels, estimated CO₂ saved, charts by plastic type/bin/day, and community totals. |

## Documentation

| Doc | What it covers |
|-----|----------------|
| [Product Requirements (PRD)](docs/PRD.md) | Problem, users, features, acceptance criteria, success metrics |
| [AGENTS.md](AGENTS.md) | Rules and structure for AI coding assistants (`CLAUDE.md` imports it) |
| [Technical Design](docs/TECHNICAL_DESIGN.md) | Architecture, data flow, AI fallback, schema, API, deployment, ADRs |
| [Data Governance & Compliance](docs/DATA_GOVERNANCE.md) | Data inventory, lineage, privacy guardrails, GDPR / DPDP / EU AI Act mapping |

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | HTML + CSS + JavaScript (Flask/Jinja templates, Chart.js) |
| Backend | Python + Flask (gunicorn in production) |
| Database | Supabase (Postgres) — falls back to local SQLite for development |
| AI | OpenRouter API, **free** vision models (auto-selected, with fallback) |
| Deployment | Render (free web service, `render.yaml` blueprint) |

## Architecture

```
Browser (HTML/CSS/JS)
   │  POST /api/scan (photo)          GET /api/stats, /api/history
   ▼
Flask backend (app.py)
   ├── services/ai.py         → resize photo → OpenRouter free vision model → JSON detections
   │                            (tries OPENROUTER_MODEL, then auto-discovered free image models,
   │                             then built-in fallbacks; skips models that are rate-limited)
   ├── services/knowledge.py  → resin codes, bins, actions, CO₂ & points (deterministic rules)
   └── services/store.py      → Supabase REST API (prod) or SQLite (local)
```

The AI only says *what* it sees; the knowledge base decides *what to do*. That keeps the
recommendations consistent and accurate whichever free model answers.

Visitors don't need an account. Each browser gets an anonymous ID (kept in `localStorage`)
so it sees its own history. The Supabase key stays on the server, and the browser never
talks to the database directly.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # then paste your OPENROUTER_API_KEY
python app.py                        # http://localhost:5000
pytest                               # run the tests
```

Without `OPENROUTER_API_KEY` the app runs in **demo mode** and returns a sample result, which
is handy for testing the UI. Without Supabase settings it stores scans in `instance/ecoscan.db`.

## Deploy (Supabase + Render)

### 1. OpenRouter (AI)
1. Sign up at <https://openrouter.ai> and create a key at <https://openrouter.ai/keys>.
2. Free models (IDs ending in `:free`) cost nothing but are rate-limited. The app picks an
   available free image model automatically. To pin one, set `OPENROUTER_MODEL`, e.g.
   `google/gemma-3-27b-it:free` (comma-separate several to set a fallback order).

### 2. Supabase (database)
1. Create a project at <https://supabase.com>.
2. Open **SQL Editor**, paste [`supabase/schema.sql`](supabase/schema.sql), and click **Run**.
3. In **Project Settings → API Keys**, copy the **Project URL** (`https://<project-id>.supabase.co`) and the
   **secret** key (`sb_secret_…`, or the legacy **service_role** key: both work).
   This key is secret: put it only in Render's environment variables, never in frontend code.

### 3. Render (hosting)
1. Push this repo to GitHub.
2. On <https://render.com>, click **New → Blueprint**, pick this repo, and Render reads `render.yaml`.
3. Fill in the environment variables when prompted:
   - `OPENROUTER_API_KEY`: your OpenRouter key
   - `SUPABASE_URL`, `SUPABASE_KEY`: from step 2
   - `APP_URL`: your Render URL, e.g. `https://ecoscan.onrender.com`
   - `OPENROUTER_MODEL`: optional
4. Deploy, then open `https://<your-app>.onrender.com/api/health`. You should see
   `"storage": "supabase", "demo": false`.

> Render's free tier sleeps after 15 minutes idle, so the first request takes about 30–50 s to wake it.
> Open the site a minute before your demo.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scan` | multipart `image` field → detection + actions (header `X-Client-Id` links it to a visitor) |
| `GET` | `/api/history` | the visitor's last 50 scans |
| `GET` | `/api/stats` | the visitor's and the community's aggregate impact |
| `GET` | `/api/health` | storage backend and demo-mode status |

## Project structure

```
app.py                  Flask app: pages + API
services/ai.py          OpenRouter vision client, model fallback, JSON parsing
services/knowledge.py   Plastic knowledge base (resins, bins, actions, CO₂, points)
services/store.py       Supabase / SQLite storage + dashboard aggregation
templates/              Home, Scan, Track (dashboard), Guide, scan detail pages
static/                 CSS, JS, bundled Chart.js
supabase/schema.sql     Database table
render.yaml             Render deployment blueprint
tests/                  pytest suite
```

## Notes and limitations
- Weights and CO₂ figures are average-based **estimates** for awareness (about 1.5 kg CO₂e saved per kg of plastic recycled).
- Recycling rules vary by city. The guidance follows common practice, so check your local rules.
- Free AI models can be slow (10–30 s) or briefly rate-limited. The app retries on other free models automatically.
