# EcoScan: Presentation Guide

A plain-language explanation of the whole project for the team, to prepare for the NeuralHack
presentation and the judges' questions. It follows the deck (`docs/presentation/EcoScan_NeuralHack.pptx`).

---

## 1. The 30-second pitch

> Most people want to recycle plastic properly, but they can't tell one plastic from another, and the
> rules differ for every item. **EcoScan** fixes that: you take a photo of your waste, an AI vision
> model finds every plastic item in it, and EcoScan tells you what each item is made of, which bin it
> goes in, and exactly what to do with it. A dashboard then tracks your scans, eco points and CO₂ saved.
> It's a live web app that works on a phone and costs nothing to run.

**Concept in four words: Detect → Understand → Act → Track.**

---

## 2. The problem (what we're solving)

| Pain point | Example |
|---|---|
| **Plastics look alike** | The resin number (#1–#7 inside the recycling triangle) is often missing or unreadable, so a PET bottle, a PP tub and a PS cup look much the same. |
| **Rules differ by item** | A PET bottle is recyclable. A thin carry bag jams sorting machines and must go to a drop-off point. A foam food box usually goes to general waste. |
| **No feedback** | People never see what their sorting achieves, so the habit doesn't stick. |

**Result:** recycling bins get contaminated and recyclable plastic ends up in landfill.

---

## 3. What the user sees (the pages)

| Page | URL | What it does |
|---|---|---|
| **Home** | `/` | Explains the four steps, lists the plastics EcoScan recognises, and shows live community totals (scans, items, kg CO₂ saved). "Scan Waste" button. |
| **Scan** | `/scan` | Upload a photo or take one with the phone camera, then tap **Analyse waste**. Shows the result: each item with its resin tag, a colour-coded bin tag, steps, a reuse idea, AI tips, the waste level, points and CO₂. Includes a "find recycling centres near me" link. |
| **Track (dashboard)** | `/dashboard` | Your eco level, points, items scanned, CO₂ saved; charts by plastic type, by bin and by day; your scan history; community totals. |
| **Guide** | `/guide` | Reference page: all 7 resin codes and the advice for every plastic category. |
| **Scan detail** | `/scan/<id>` | Opens a past scan with its full result again. |

**No login.** Each browser gets a random anonymous ID (kept in `localStorage`), so you see only your own history.

---

## 4. What happens when you tap "Analyse waste"

This is the most important thing to be able to explain.

```
 Phone / laptop                      Flask server (Render)                         Outside services
 ──────────────                      ─────────────────────                         ────────────────
 1. Photo + anonymous ID  ─────────► 2. Check it's an image (JPG/PNG/WEBP…, ≤10 MB)
                                     3. Prepare image: fix rotation, shrink to
                                        1024 px, re-save as JPEG (drops EXIF/GPS),
                                        make a 320 px thumbnail
                                     4. Send the photo + prompt  ───────────────► OpenRouter free
                                                                                   vision model
                                     5. Get JSON back: items, category, resin,  ◄──┘
                                        count, confidence, condition, summary, tips
                                        (if a model fails → try the next one, up to 3)
                                     6. Knowledge base (enrich): add bin, steps,
                                        reuse idea, weight, CO₂, points, waste level
                                     7. Save thumbnail + analysis ──────────────► Supabase (Postgres)
                                        (if saving fails, still show the result)
 9. Result shown on screen  ◄─────── 8. Return the full result as JSON
```

### The key design idea: "The AI detects, the knowledge base decides"

- The **AI** only answers *"what plastic items are in this photo?"* It returns a small, fixed JSON format.
- **Our own rules** (`services/knowledge.py`) decide the bin, the steps, CO₂ and points.
- **Why:** free AI models vary in quality and sometimes make things up. With this split, the same item
  always gets the same, correct advice, whichever model answered. The model output is also treated as
  untrusted: counts are limited to 1–500, confidence to 0–1, unknown categories become "other", and
  invalid resin numbers are replaced with the category's usual one.

---

## 5. What each file does

| File / folder | In plain words |
|---|---|
| `app.py` | The web server. Defines the pages (`/`, `/scan`, `/dashboard`, `/guide`) and the API (`/api/scan`, `/api/history`, `/api/stats`, `/api/health`). Handles errors (bad upload → 400, too large → 413, AI failed → 502, database down → 503). |
| `services/ai.py` | Talks to the AI. Prepares the image, holds the **prompt**, picks which free models to try, calls OpenRouter, pulls the JSON out of the reply. Also has the **demo result** used when no API key is set. |
| `services/knowledge.py` | The "brain" of the recycling advice: the 7 resin codes, 8 plastic categories, 3 bin types, points, waste levels and the CO₂ factor. `enrich()` turns the AI's raw answer into the final result. |
| `services/store.py` | Saves and reads scan history. Uses **Supabase** in production and a local **SQLite** file for development (same functions for both). Also calculates dashboard totals and eco levels. |
| `templates/` | The HTML pages (Jinja templates). `base.html` is the shared layout (nav bar, footer). |
| `static/css/style.css` | All the styling, including dark mode and phone layout. |
| `static/js/common.js` | Shared helpers: `api()` sends requests with the anonymous ID, `esc()` makes text safe to display. |
| `static/js/scan.js` | Upload screen and drawing the result cards. |
| `static/js/dashboard.js` | Dashboard numbers, charts (Chart.js) and history list. |
| `supabase/schema.sql` | Creates the `scans` database table. |
| `tests/test_app.py` | 11 automated tests (all passing). They never call the real AI or database. |
| `render.yaml` | Deployment settings for Render. |
| `docs/` | PRD (requirements), technical design, data governance, and this guide. |

---

## 6. Key concepts explained

### 6.1 Plastic categories (8)
Bottle · bag · food container · packaging/wrapper · cup · straw/cutlery · jug/detergent bottle (HDPE) · other.

### 6.2 Resin codes (the number in the recycling triangle)

| # | Code | Material | Recyclable? | Examples |
|---|---|---|---|---|
| 1 | PET | Polyethylene terephthalate | Widely | Water & soda bottles |
| 2 | HDPE | High-density polyethylene | Widely | Milk jugs, shampoo bottles |
| 3 | PVC | Polyvinyl chloride | Rarely | Pipes, blister packs |
| 4 | LDPE | Low-density polyethylene | Drop-off | Carry bags, films |
| 5 | PP | Polypropylene | Often | Food tubs, bottle caps |
| 6 | PS | Polystyrene | Rarely | Foam cups, clamshells |
| 7 | Other | Mixed plastics | Rarely | Multi-layer pouches |

### 6.3 Bins (3) and points per item

| Bin | Meaning | Points |
|---|---|---|
| **Recycle** (blue) | Dry recyclables bin | 10 |
| **Drop-off point** (amber) | e.g. supermarket soft-plastic collection | 8 |
| **General waste** (grey) | Not recyclable | 3 |

Special rules: a food container made of #3, #6 or #7 (e.g. foam) goes to **general waste**; a cup made of
clear #1 or #5 goes to **recycle**.

### 6.4 Waste level (per photo, by total item count)
0 = none · 1–3 = **low** · 4–9 = **medium** · 10+ = **high** (suggests a clean-up drive).

### 6.5 CO₂ saved (an estimate)
`weight = average item weight × count`, and `CO₂ saved = weight × 1.5 kg CO₂e per kg`, counted only for
items that are recycled or dropped off. 1.5 is a conservative figure from the typical range of 1–2.5.
Always call it an **estimate**.

### 6.6 Eco levels (from total points)
Seedling 🌱 (0) → Sprout 🌿 (50) → Tree 🌳 (150) → Forest 🌲 (400) → Earth Guardian 🌍 (1000).

### 6.7 Model fallback
Free AI models are rate-limited and sometimes go offline. EcoScan builds a list: models you configure
(`OPENROUTER_MODEL`) → free image models it finds automatically on OpenRouter → a built-in backup list.
It tries up to **3** and moves on after an error or an unreadable answer. It stops at once on a bad key
(401) or no credit (402), because other models won't help.

### 6.8 Demo mode
With no `OPENROUTER_API_KEY`, the app returns a fixed sample result, so the UI can always be shown.

### 6.9 Privacy
No accounts, no names or emails. The full photo is never stored. EXIF data (including GPS location) is
removed. Only a small 320 px thumbnail and the analysis are saved. The database key stays on the server,
and the browser never talks to the database directly (row-level security is on).

---

## 7. Worked example (the one on the Solution slide)

Photo: 2 water bottles, 1 carry bag, 1 takeaway box.

| Item | Resin | Bin | Weight | CO₂ saved | Points |
|---|---|---|---|---|---|
| Water bottle ×2 | #1 PET | Recycle | 2 × 25 g = 50 g | 0.050 × 1.5 = 0.075 kg | 2 × 10 = 20 |
| Carry bag | #4 LDPE | Drop-off | 6 g | 0.006 × 1.5 = 0.009 kg | 8 |
| Takeaway box | #5 PP | Recycle | 30 g | 0.030 × 1.5 = 0.045 kg | 10 |
| **Total** | | | **86 g** | **≈ 0.13 kg** | **38** |

4 items → waste level **MEDIUM**. All 4 are recyclable (none go to general waste).

---

## 8. Slide-by-slide speaker notes

**Slide 1: Title.** Introduce the team and the one-line idea: *"Photo in, per-item recycling guidance out."*

**Slide 2: Problem.** Walk through the three cards (plastics look alike, rules differ, no feedback), then the
result: contaminated recycling and plastic in landfill. Ask the audience: *"Does a foam food box go in the
recycling bin?"* Most people guess wrong.

**Slide 3: Solution.** Explain Detect → Understand → Act → Track in one sentence each, then read the example
scan across the bottom: two bottles go to recycling, the bag goes to a drop-off point, the box is recycled,
and the user earns 38 points and saves about 0.13 kg CO₂.

**Slide 4: Approach & Tech Stack.** Trace the diagram from top to bottom: browser → Flask API → AI vision,
knowledge base and storage. Stress the key idea: *the AI detects, the knowledge base decides*, which keeps
advice consistent. Then the stack: HTML/CSS/JS, Python Flask, OpenRouter free vision models, Supabase,
Render, pytest.

**Slide 5: Impact.** The four numbers: ₹0 to run, 100% of items get a bin and steps, 7 resin codes and
8 categories, 3-model fallback. Who benefits: households, eco-clubs and students, campus and office staff.
Close on the outcome: cleaner recycling, visible CO₂ savings, and privacy by default.

**Slide 6: Thank you.** Show the GitHub link and offer a live demo.

---

## 9. Likely judge questions and answers

| Question | Answer |
|---|---|
| **Did you train your own model?** | No. We use pre-trained free vision models through OpenRouter. The novelty is the pipeline: a strict prompt, defensive parsing, model fallback, and a rule-based knowledge base that turns detections into reliable actions. |
| **What if the AI is wrong?** | The advice itself can't be wrong for a given category, because it comes from our rules. The AI can misidentify an item, so we show a confidence score, and the user can see the resin tag and check the number on the item. |
| **What if the AI is down or rate-limited?** | It automatically tries the next free model (up to 3). If all fail, the user gets a friendly "try again in a minute" message and nothing broken is saved. Demo mode works without any AI at all. |
| **Why not just ask the AI what to do with each item?** | Free models give different, sometimes invented answers. Keeping decisions in our own rules makes the advice consistent, testable and easy to correct. |
| **How accurate is it?** | Our target is at least 80% correct category and 90% plastic/no-plastic on a 30-photo test set (see PRD §7). *(Only quote measured numbers if you have run this test.)* |
| **How is CO₂ calculated?** | Average item weight × count × 1.5 kg CO₂e per kg, only for recycled or dropped-off items. It's labelled as an estimate. |
| **What about privacy?** | No accounts or personal details. The original photo is never stored, EXIF/GPS is removed, only a small thumbnail is kept, and the database key never reaches the browser. |
| **What does it cost?** | Nothing: free OpenRouter models, the free Supabase tier and the free Render tier. |
| **Why the web and not an app?** | A web app works on any phone with the camera, with nothing to install, and deploys in minutes. |
| **Does it draw boxes around items?** | Not in v1. It lists items with counts. Bounding boxes are on the roadmap. |
| **Do rules differ by city?** | Yes. v1 follows common practice and tells users to check local rules. City-specific rule packs are the first roadmap item. |
| **How did you test it?** | 11 automated pytest tests covering pages, scanning, AI failure, bad uploads, the recycling rules, JSON parsing, model fallback and the database layer. The AI and database are mocked in tests. |

---

## 10. Limitations and roadmap

**Current limitations:** no bounding boxes; one set of general rules (not city-specific); CO₂ and weights
are averages; free models can be slow (the target is under 45 s per scan) and vary in accuracy; history is tied to one browser.

**Roadmap:** city-specific rule packs → map of nearby recycling centres → bounding boxes on the photo →
optional accounts with "delete my data" → clean-up drive reports for NGOs → multilingual UI and voice guidance.

---

## 11. Demo checklist

1. **Open the live site about a minute before presenting.** Render's free tier sleeps after 15 minutes idle,
   and the first request takes 30–50 s.
2. Check `/api/health` shows `"storage": "supabase", "demo": false`.
3. Have 2–3 test photos ready on the phone (e.g. a bottle + a bag + a food box) and a backup in case of
   slow Wi-Fi.
4. Show: Home → Scan (take a photo) → result cards → Track dashboard → Guide.
5. If the AI is slow or fails, explain the fallback and show a past scan from the dashboard.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **OpenRouter** | A service that gives one API to many AI models, including free ones. |
| **Vision model** | An AI model that can look at images and describe them. |
| **Flask** | A lightweight Python web framework (our backend). |
| **Jinja template** | An HTML file with placeholders that Flask fills in. |
| **Supabase** | A hosted Postgres database; we use its REST API. |
| **SQLite** | A database stored in a single file, used for local development. |
| **Render** | The cloud platform that hosts the app. |
| **API** | The URLs the frontend calls to get data (`/api/scan` etc.). |
| **EXIF** | Hidden photo metadata (camera, time, GPS location); we remove it. |
| **Resin code** | The number 1–7 in the recycling triangle that says which plastic an item is made of. |
| **CO₂e** | "CO₂ equivalent", a standard unit for climate impact. |
| **Rate limit** | A cap on how many requests a free service allows per minute. |
| **Demo mode** | The app returns a sample result when no AI key is configured. |
