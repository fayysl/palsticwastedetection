# Technical Design Document — EcoScan

**Scope:** architecture, data model, API, AI integration and deployment for EcoScan v1.
**Related:** requirements in [PRD.md](PRD.md) · agent rules in [../AGENTS.md](../AGENTS.md) · privacy in [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)

---

## 1. Architecture overview

```
┌──────────────────────────── Browser ─────────────────────────────┐
│  Jinja-rendered pages (Home · Scan · Track · Guide · Scan detail) │
│  static/js: common.js (api, esc, client id) · scan.js · dashboard │
│  localStorage: ecoscan-client-id  (anonymous UUID)                │
└───────────────┬───────────────────────────────▲──────────────────┘
                │ multipart photo / JSON        │ JSON / HTML
                │ header X-Client-Id            │
┌───────────────▼───────────────────────────────┴──────────────────┐
│  Flask app (app.py · create_app) on gunicorn, Render web service │
│                                                                  │
│  services/ai.py ── prepare_image ─► detect ──────────────────────┼──► OpenRouter API
│        (resize 1024px, strip EXIF,   (model fallback loop,       │    (free vision models)
│         320px thumbnail)              JSON parsing)              │
│                    │                                             │
│  services/knowledge.py ── enrich(detection) ─► analysis          │
│        (resin, bin, actions, CO₂, points, waste level)           │
│                    │                                             │
│  services/store.py ── SupabaseStore | SQLiteStore ───────────────┼──► Supabase Postgres (REST)
│        (save / list / get, summarize for dashboards)             │    or instance/ecoscan.db
└──────────────────────────────────────────────────────────────────┘
```

**Key principle:** the model's job is *perception* (what is in the photo). *Decisions* (what to
do about it) are deterministic code in `knowledge.py`, so advice is consistent, testable and safe
from model mistakes.

## 2. Tech stack decisions

| Decision | Choice | Why | Alternatives rejected |
|----------|--------|-----|-----------------------|
| Web framework | Flask 3 + Jinja | Mandated stack; small; one deployable unit | FastAPI (unnecessary async), Django (heavy) |
| Frontend | Server-rendered HTML + vanilla JS | Mandated; no build step; fast first load on Render's free tier | React SPA (build tooling, out of scope) |
| Charts | Chart.js 4, vendored | Works offline and without a CDN; one file | CDN (can fail on demo networks) |
| AI provider | OpenRouter, free vision models | $0 cost; one API for many models; a fallback exists when one model is busy | A single paid provider |
| Model choice | Auto-discovery + fallback list | Free models appear and disappear; avoids hard-coding a dead model | One fixed model ID |
| DB | Supabase Postgres via PostgREST + `requests` | Free hosted Postgres; REST needs no SDK; JSONB for analysis | `supabase-py` (heavy deps), Firebase (not relational) |
| Local DB | SQLite | Zero setup; same interface as Supabase | — |
| Image storage | 320 px JPEG thumbnail as a data URL in the row | No storage bucket to configure; ~15 KB per row; privacy (no full image kept) | Supabase Storage bucket |
| Identity | Anonymous per-browser UUID | No login friction at a hackathon; no personal data | Supabase Auth (out of scope for v1) |
| Hosting | Render free web service + `render.yaml` | Git-push deploys; Python native; health checks | Vercel (serverless time limits hurt slow free models) |

## 3. Components

### 3.1 `app.py`
- `create_app(store=None)` builds the app. Injecting a store makes testing easy.
- Config: `MAX_CONTENT_LENGTH = 10 MB`. MIME allow-list: jpeg, png, webp, heic/heif, gif.
- `client_id()` accepts `X-Client-Id` only if it matches `^[A-Za-z0-9-]{8,64}$`.
- Demo mode is on when `OPENROUTER_API_KEY` is unset. The template flag `demo_mode` shows a banner.

### 3.2 `services/ai.py`
- `prepare_image(bytes)`: open with Pillow → `exif_transpose` (fix phone rotation) → RGB → downscale
  to 1024 px on the longest side → JPEG q85 (re-encoding **drops EXIF, including GPS**). Also makes a
  320 px JPEG q70 thumbnail as a `data:` URL.
- `candidate_models()`: `OPENROUTER_MODEL` (comma list) → `discover_free_vision_models()` → `FALLBACK_MODELS`,
  de-duplicated in that order.
- `discover_free_vision_models()`: `GET /api/v1/models` (public). Keeps models whose prompt and completion
  prices are `"0"` and whose `input_modalities` include `image`. Cached for 1 hour. If the request fails, it returns `[]`.
- `detect(jpeg, max_attempts=3, timeout=45)`: see §5.
- `parse_json(text)`: strips ```` ```json ```` fences, then tries `json.loads`, then the outermost `{…}` substring.

### 3.3 `services/knowledge.py`
- `RESINS` (1–7), `CATEGORIES` (8), `BINS` (recycle / drop_off / general), `POINTS`, `LEVELS`, `CO2_SAVED_PER_KG = 1.5`.
- `enrich(detection) -> analysis`: see §6.

### 3.4 `services/store.py`
- The same interface on both backends: `save(client_id, analysis, thumbnail, model, demo) -> row`, `list(client_id|None, limit)`, `get(id)`.
- `make_store()` uses Supabase if `SUPABASE_URL` and `SUPABASE_KEY` are set, otherwise SQLite at `SQLITE_PATH` or `instance/ecoscan.db`.
- `summarize(rows)` builds the dashboard aggregates. `eco_level(points)` gives the tier name and the next threshold.

### 3.5 Frontend
- `common.js`: `getClientId()` (a UUID in localStorage), `api()` (fetch wrapper that adds `X-Client-Id` and throws `error` messages), `esc()` for HTML escaping.
- `scan.js`: file picker (`capture="environment"` opens the rear camera on phones), drag and drop, client-side type and size checks, `renderResult(scan)`.
- `dashboard.js`: KPIs, 3 charts (items by type, bin split, items per day), history list linking to `/scan/<id>`.

## 4. Data flow: a scan

```
User            Browser (scan.js)           Flask /api/scan                OpenRouter          Store
 │ pick photo ──► client checks (image/*, ≤10MB)
 │ Analyse ─────► POST multipart image + X-Client-Id
 │                                   ├─ MIME allow-list, size limit (413)
 │                                   ├─ prepare_image → 1024px JPEG + thumbnail (400 if unreadable)
 │                                   ├─ demo? → DEMO_DETECTION
 │                                   ├─ else detect() ─────────────► chat/completions (model 1)
 │                                   │                 ◄──── 429 / bad JSON → try model 2, 3
 │                                   │                 ◄──── 200 JSON
 │                                   ├─ knowledge.enrich(detection)
 │                                   ├─ store.save(...) ───────────────────────────────────► insert row
 │                                   │     (on failure: add save_error, continue)
 │  result ◄──── renderResult(scan) ◄┘ 200 {id, demo, model, thumbnail, analysis, created_at}
```

## 5. AI integration

### 5.1 Request
`POST https://openrouter.ai/api/v1/chat/completions`, with headers `Authorization: Bearer <key>`,
`HTTP-Referer: $APP_URL` and `X-Title: EcoScan Plastic Detector`. The body sets `temperature 0.1` and sends one user
message with a text part (the prompt) and an `image_url` part (a base64 JPEG data URL).

### 5.2 Prompt contract (model → server)
```json
{
  "items": [
    {"name": "Clear water bottle", "category": "bottle", "resin_code": 1,
     "count": 2, "confidence": 0.93, "condition": "clean"}
  ],
  "summary": "one sentence",
  "tips": ["up to 3 practical tips"]
}
```
`category` ∈ `bottle, bag, food_container, packaging, cup, cutlery_straw, container_hdpe, other`.
The prompt tells the model to list plastic only, to return `items: []` when no plastic is present, and to use JSON only.

### 5.3 Fallback algorithm
```
for model in candidate_models()[:3]:
    POST (timeout 45 s)
    401/402            → stop (key/credit problem; other models won't help)
    other non-200      → next model
    body.error         → next model
    content unparsable → next model
    success            → return (detection, served_model)
raise AIError → HTTP 502 "All AI models failed … try again in a minute"
```
Worst case is about 3 × 45 s = 135 s. gunicorn runs with `--timeout 180`.

## 6. Enrichment rules (`knowledge.enrich`)

| Input problem | Rule |
|---------------|------|
| Unknown `category` | → `other` |
| `resin_code` missing, non-numeric or not 1–7 | → the category's `default_resin` |
| `count` | int, clamped to 1–500 |
| `confidence` | float, clamped to 0–1, default 0.7 |
| Strings | name ≤ 80, condition ≤ 30, summary ≤ 400, each tip ≤ 200 (max 3) |
| Non-dict items | skipped |

Bin overrides: `food_container` with resin 3, 6 or 7 → **general**. `cup` with resin 1 or 5 → **recycle**.

Derived values:
- `weight_kg = avg_weight_g × count / 1000`
- `co2_saved_kg = weight_kg × 1.5`, or 0 if the bin is general
- `points = POINTS[bin] × count` (recycle 10, drop-off 8, general 3)
- `level` from total items: 0 → none, 1–3 → low, 4–9 → medium, ≥ 10 → high
- Eco tiers by total points: Seedling 0, Sprout 50, Tree 150, Forest 400, Earth Guardian 1000

## 7. Data model

**Table `public.scans`** (`supabase/schema.sql`; SQLite mirrors it, storing `analysis` as JSON text)

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | generated server-side (`uuid4`) |
| `client_id` | text | anonymous browser ID, nullable |
| `created_at` | timestamptz | UTC ISO-8601 |
| `thumbnail` | text | `data:image/jpeg;base64,…`, 320 px |
| `model` | text | model that answered, or `demo` |
| `demo` | boolean | true for demo-mode scans |
| `total_items` | integer | |
| `recyclable_items` | integer | items not in the general bin |
| `co2_saved_kg` | double | |
| `points` | integer | |
| `level` | text | none / low / medium / high |
| `analysis` | jsonb | the full `enrich()` output (below) |

Indexes: `(client_id, created_at desc)` and `(created_at desc)`. **RLS is enabled with no policies**, so
only the backend's `service_role` key can read or write.

**`analysis` JSON:**
```json
{
  "plastic_detected": true, "summary": "…", "total_items": 4, "recyclable_items": 4,
  "level": {"key": "medium", "text": "Medium — several items, segregate before disposal"},
  "total_weight_kg": 0.086, "co2_saved_kg": 0.129, "points": 38, "tips": ["…"],
  "items": [{
    "name": "Clear water bottle", "category": "bottle", "icon": "🥤", "count": 2,
    "confidence": 0.93, "condition": "clean",
    "resin": {"number": 1, "code": "PET", "name": "Polyethylene terephthalate",
              "recyclable": "widely", "examples": "…"},
    "bin": {"key": "recycle", "label": "Recycle", "color": "#2563eb"},
    "segregation": "Dry recyclables (blue bin)", "actions": ["…"], "reuse": "…",
    "weight_kg": 0.05, "co2_saved_kg": 0.075, "points": 20
  }]
}
```

## 8. API specification

All endpoints return JSON. Errors are `{"error": "message"}`. Visitor identity comes from the optional `X-Client-Id` header.

| Method & path | Request | 200 response | Errors |
|---------------|---------|--------------|--------|
| `POST /api/scan` | multipart `image` | `{id, demo, model, thumbnail, analysis, created_at}` plus optional `save_error` | 400 no file, bad type or unreadable · 413 > 10 MB · 502 all AI models failed |
| `GET /api/history` | — | `{scans:[{id, created_at, thumbnail, total_items, co2_saved_kg, points, level, demo, summary}]}` (latest 50; empty without a valid client ID) | 503 storage |
| `GET /api/stats` | — | `{mine: Summary, community: Summary, category_labels}` | 503 storage |
| `GET /api/health` | — | `{ok, storage: "supabase"\|"sqlite", demo}` | — |

`Summary = {scans, items, recyclable_items, co2_saved_kg, points, eco_level:{name,next_at}, by_category, by_bin, daily}`.
`mine` covers the latest 500 scans for the client. `community` covers the latest 1,000 scans overall.

**Pages:** `/`, `/scan`, `/dashboard`, `/guide`, `/scan/<id>` (404 if missing, 503 on a storage error).

## 9. Configuration

| Env var | Required | Purpose |
|---------|----------|---------|
| `OPENROUTER_API_KEY` | for real scans | Demo mode if unset |
| `OPENROUTER_MODEL` | no | Comma-separated models to try first |
| `SUPABASE_URL`, `SUPABASE_KEY` | in production | Supabase project URL + `service_role` key. SQLite is used if unset |
| `APP_URL` | no | Sent as `HTTP-Referer` to OpenRouter |
| `SQLITE_PATH` | no | Override the SQLite file path |
| `PORT` | set by Render | Bind port |
| `FLASK_DEBUG` | no | `1` enables the debugger (local only) |

## 10. Deployment

- **Render** blueprint `render.yaml`: `pip install -r requirements.txt`, then
  `gunicorn app:app --workers 2 --threads 4 --timeout 180`, with health check `/api/health`, Python 3.11.9.
- **Supabase:** run `supabase/schema.sql` once.
- Render's free-tier disk is ephemeral, so **SQLite data is lost on restart**. Production must use Supabase.
- The free tier sleeps after 15 minutes idle, so the first request cold-starts in about 30–50 s.

## 11. Security

| Concern | Control |
|---------|---------|
| Secrets | Env vars only; `.env` is git-ignored; `service_role` key never reaches the browser |
| DB access | RLS on, no policies, so the public anon key can't read the table |
| XSS from model output | All dynamic text goes through `esc()` before `innerHTML`; Jinja auto-escaping; `tojson` for the detail page |
| Upload abuse | 10 MB limit, MIME allow-list, Pillow decode check, re-encode to JPEG |
| Header spoofing | `X-Client-Id` is format-validated. It is a convenience identifier, **not authentication** |
| Scan detail URLs | `/scan/<uuid>` is readable by anyone who has the unguessable UUID ("unlisted link" model) |
| **Known gaps** | No rate limiting on `/api/scan`; no delete endpoint; `client_id` can be copied by anyone with access to the browser. See the roadmap |

## 12. Performance

- Images are downscaled to 1024 px before upload to the model, which cuts token cost and latency.
- Model discovery is cached for 1 hour.
- `/api/stats` aggregates in Python over at most 1,000 + 500 rows, which is fine for hackathon scale.
  **Scale path:** a Postgres view or RPC for aggregates, and selecting without `thumbnail`.

## 13. Testing strategy

`pytest -q` runs `tests/test_app.py`, with all external calls mocked:
- pages render; demo scan saves, then shows in history, stats and the detail page; history is isolated per client
- a real-mode scan uses `ai.detect`; AI failure → 502; bad uploads → 400
- `enrich()` edge cases (foam container, bad resin, unknown category, garbage items)
- `parse_json` handles fences and chatter; `detect()` falls back from a 429 model to the next
- `SupabaseStore` sends the correct URL, headers and filters

**Manual checks before a demo:** `/api/health` shows `storage: supabase, demo: false`; scan 3 real photos
(bottle, bag, no plastic); check the layout at phone width.

## 14. Architecture decision records (summary)

| ADR | Decision |
|-----|----------|
| 001 | Separate perception (LLM) from decisions (rules) for consistency and testability |
| 002 | Use OpenRouter free models with discovery + fallback instead of one pinned model |
| 003 | Talk to Supabase over REST with `requests`, no SDK |
| 004 | Store a thumbnail only, not the original photo (privacy + no bucket setup) |
| 005 | Anonymous browser IDs instead of accounts for v1 |
| 006 | Vendor Chart.js; no frontend build step |
