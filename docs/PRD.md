# Product Requirements Document — EcoScan

**Product:** EcoScan — Intelligent Plastic Waste Detection and Environmental Action System
**Status:** v1 (hackathon build) · **Owner:** Team EcoScan · **Last updated:** 2026-09-30

---

## 1. Problem statement

People want to dispose of plastic responsibly but don't know how. Plastic types look alike, the resin
number is often missing or unreadable, and recycling rules differ by item (a PET bottle is recyclable,
a thin carry bag jams sorting machines, a foam food box usually goes to general waste). The result is
contaminated recycling streams and recyclable plastic sent to landfill.

**Goal:** develop an AI-based system that **detects plastic waste from images**, identifies the **type and
level** of waste, and provides **environmental actions** such as segregation, recycling or disposal
recommendations.

## 2. Product concept: Detect → Understand → Act → Track

| Stage | User value |
|-------|-----------|
| **Detect** | "What plastic is in this photo?" |
| **Understand** | "What is it made of, can it be recycled, and how much waste is this?" |
| **Act** | "What exactly should I do with each item right now?" |
| **Track** | "What impact have I made over time?" |

## 3. Target users

| Persona | Need | How EcoScan helps |
|---------|------|-------------------|
| **Household member** | Sort kitchen and home waste correctly | Photo → per-item bin and steps |
| **Student / eco-club volunteer** | Run clean-up drives and report results | Waste level, item counts, community totals |
| **Office / campus facilities staff** | Train people on segregation | Plastic guide + consistent recommendations |
| **Hackathon judges** | See a working, deployed end-to-end AI product | Live URL, demo mode, dashboard |

## 4. Scope

### 4.1 In scope (v1)

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| F1 | **AI Plastic Scanner**: upload a photo or take one with the phone camera ("Scan Waste") | P0 | ✅ |
| F2 | Detect item categories: bottle, bag, food container, packaging, cup, straw/cutlery, jug/HDPE container, other | P0 | ✅ |
| F3 | Identify resin code #1–#7 (PET, HDPE, PVC, LDPE, PP, PS, Other) per item | P0 | ✅ |
| F4 | Waste level: none / low / medium / high, based on item count | P0 | ✅ |
| F5 | Per-item actions: segregation bin, numbered disposal/recycling steps, reuse idea | P0 | ✅ |
| F6 | Photo-specific AI tips (up to 3) | P1 | ✅ |
| F7 | "Find recycling centres near me" link | P1 | ✅ |
| F8 | Track dashboard: history, eco points, eco level, CO₂ saved, charts by type/bin/day | P0 | ✅ |
| F9 | Community impact totals across all users | P2 | ✅ |
| F10 | Plastic recycling guide page (resin codes + per-category guidance) | P1 | ✅ |
| F11 | Demo mode when no AI key is configured | P1 | ✅ |
| F12 | Mobile-friendly UI (phone camera capture, 390 px layout) | P0 | ✅ |

### 4.2 Out of scope (v1): non-goals

- User accounts and login. Each browser gets an anonymous ID instead.
- Bounding boxes or pixel-level segmentation of items.
- Training or fine-tuning a custom model.
- Location-aware, city-specific recycling rules.
- Rewards redemption, leaderboards, social sharing.
- The "Secure File Sharing with Expiring Links" problem statement. That is a separate hackathon track.

## 5. User stories and acceptance criteria

**US1 — Scan.** *As a user, I want to photograph my waste and learn what plastic it contains.*
- Given a JPG/PNG/WEBP photo of up to 10 MB, when I tap **Analyse waste**, then I see a list of the detected plastic items with name, count, confidence and condition.
- If the photo has no plastic, I see "No plastic detected" and a hint to retake the photo.
- If the file is not an image or is too large, I see a clear error, not a crash.

**US2 — Understand.** *As a user, I want to know what each item is made of and whether it's recyclable.*
- Each item shows a resin tag (e.g. `#1 PET`) and a colour-coded bin tag (Recycle / Drop-off point / General waste).
- The result shows the overall waste level with a one-line explanation.

**US3 — Act.** *As a user, I want clear instructions for each item.*
- Each item shows a segregation line, 2–3 numbered steps and a reuse idea.
- The same item category and resin always produce the same guidance, whichever AI model ran.
- Foam (#6) food containers go to general waste. Clear #1/#5 cups go to recycling.

**US4 — Track.** *As a user, I want to see my environmental impact.*
- Each scan is saved to my history (per browser) and the dashboard updates its KPIs and charts.
- I can open any past scan and see its full result again.
- Other visitors cannot see my history list.

**US5 — Resilience.** *As a demo presenter, I need the app to work even when a free AI model is overloaded.*
- If a model is rate-limited or returns invalid output, the system tries the next free model automatically, up to 3 attempts.
- If every attempt fails, the user sees "please try again in a minute" (HTTP 502), and nothing is saved.
- If the database is down, the scan result is still shown, with a "could not be saved" notice.

## 6. Expected behaviour: example

Input: a photo of 2 water bottles, 1 carry bag and 1 takeaway box.

| Item | Resin | Bin | Key action |
|------|-------|-----|-----------|
| Clear water bottle ×2 | #1 PET | Recycle | Empty, rinse, crush, cap on → blue bin |
| Thin carry bag | #4 LDPE | Drop-off point | Not curbside; return to a supermarket soft-plastic drop-off |
| Takeaway food box | #5 PP | Recycle | Scrape food, rinse grease, then recycle |

Summary: **4 items · waste level MEDIUM · 4 recyclable · ≈0.13 kg CO₂ saved · +38 eco points.**

## 7. Success metrics

| Metric | Target (v1) | How measured |
|--------|-------------|--------------|
| Category accuracy | ≥ 80 % of items correctly categorised on a 30-photo test set | Manual labelled test set |
| Plastic/no-plastic accuracy | ≥ 90 % | Same test set, including 5 non-plastic photos |
| Scan latency | p50 ≤ 20 s, p95 ≤ 45 s on free models | Server logs / stopwatch |
| Scan success rate | ≥ 95 % of scans return a result (no 502) | `/api/scan` status codes |
| Actionability | 100 % of detected items show a bin + steps | Guaranteed by the knowledge base; covered by tests |
| Engagement (demo) | ≥ 3 scans per test user; dashboard opened after scanning | Scan counts per `client_id` |
| Reliability | Health check green on the deployed URL | `GET /api/health` |

## 8. Constraints and assumptions

- **Cost:** ₹0 / $0. Free OpenRouter models, free Supabase and Render tiers.
- **Free-model limits:** rate limits and variable quality are expected, so the design must tolerate model failures (see US5).
- **Estimates:** weight and CO₂ figures are average-based (≈1.5 kg CO₂e saved per kg recycled) and are labelled as estimates in the UI.
- **Rules vary locally:** the guidance follows common practice. Users are told to check local rules.
- **Stack (mandated):** HTML + CSS + JS frontend, Python + Flask backend, Supabase database, AI via API, deployed on Render.

## 9. Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Free model misclassifies items | Wrong advice | Structured prompt; knowledge base constrains output to known categories; confidence shown |
| Free model offline or rate-limited during judging | Demo fails | Multi-model fallback; demo mode; open the site before presenting (Render cold start) |
| Users upload photos containing people | Privacy | See [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md): EXIF stripped, small thumbnail only, no accounts |
| Inflated CO₂ claims | Credibility | Conservative factor, "estimate" labels |

## 10. Roadmap (post-hackathon)

1. City-specific rule packs (choose a city → bin names and rules adapt).
2. Map of nearby recycling and drop-off centres (instead of a Maps search link).
3. Bounding boxes drawn on the photo.
4. Optional accounts to sync history across devices, and a "delete my data" button.
5. Clean-up drive mode: group scans into an event report for NGOs and municipalities.
6. Multilingual UI (e.g. Urdu/Hindi) and voice guidance.
