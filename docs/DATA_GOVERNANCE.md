# Data Governance & Compliance — EcoScan

**Purpose:** record what data EcoScan handles, where it comes from and goes, how it is protected,
and how that maps to privacy and AI regulations.
**Status:** v1 (hackathon build). Items marked **Implemented** are in the code today. Items marked
**Recommended** are not built yet and should be done before any real-world launch.

> This document is an engineering record, not legal advice. Get a legal review before running
> EcoScan as a public production service.

---

## 1. Data inventory

| Data | Source | Where it goes | Stored? | Retention | Personal data? |
|------|--------|---------------|---------|-----------|----------------|
| Uploaded photo (original) | User upload | Flask memory only | **No**. Discarded after the request | Request lifetime | Possibly (people, faces, house interiors, documents) |
| Resized photo (≤1024 px JPEG, **EXIF removed**) | Derived on the server | Sent to OpenRouter and the selected model provider | Not by EcoScan. See §3 for the provider | Provider policy | Possibly |
| Thumbnail (320 px JPEG) | Derived on the server | Supabase `scans.thumbnail` | Yes | Indefinite (**Recommended:** 90 days) | Possibly (low resolution) |
| Photo metadata (EXIF: GPS, device, time) | Inside the upload | **Dropped** during re-encoding | No | — | Yes (location) |
| `client_id` (random UUID) | Generated in the browser (`localStorage`) | Supabase `scans.client_id` | Yes | Same as the scan | Pseudonymous identifier (treated as personal data under GDPR) |
| AI analysis (items, summary, tips) | Model output + knowledge base | Supabase `scans.analysis` | Yes | Same as the scan | Normally no. The summary could describe a person in the photo |
| Model name, demo flag, derived stats | Server | Supabase | Yes | Same as the scan | No |
| IP address, user agent | HTTP request | Render platform logs | Not by the app | Render log retention | Yes |
| Names, emails, passwords, payment data | — | — | **Never collected** | — | — |

## 2. Data lineage

```
Phone/PC photo ──(HTTPS)──► Flask (Render)
                               │ decode → rotate → resize → re-encode JPEG (EXIF stripped)
                               ├──► OpenRouter ──► model provider (free tier) ──► JSON detection
                               │                                                   │
                               │ ◄──────────────────────────────────────────────── ┘
                               │ knowledge.enrich()  (deterministic rules, no personal data)
                               ├──► Supabase Postgres: thumbnail + analysis + client_id
                               └──► Browser: result JSON (rendered with HTML escaping)
Original photo bytes are never written to disk or the database.
```

## 3. AI model and knowledge sources

| Component | Source | Notes |
|-----------|--------|-------|
| Vision model | Third-party pre-trained models served through **OpenRouter** (free `:free` models, auto-selected) | EcoScan does **not train or fine-tune** any model. The model that answered is saved in `scans.model` for traceability |
| Prompt | `services/ai.py` `PROMPT` (version-controlled) | Asks for plastic items only, as JSON |
| Recycling knowledge | Hand-written rules in `services/knowledge.py` (standard resin identification codes 1–7 and common segregation practice) | Version-controlled; reviewed through git history |
| CO₂ factor | 1.5 kg CO₂e saved per kg recycled (a conservative mid-range life-cycle figure) | Shown to users as an "estimate" |
| Training data | **None collected.** User scans are not used to train anything | |
| Retrieval data (RAG) | None | |

**Third-party processing: important.** Photos go to OpenRouter and then to whichever provider serves the chosen free model.
Some free endpoints may **log prompts or use inputs to improve their models**, depending on the provider and your
OpenRouter privacy settings.
- **Recommended:** in OpenRouter → Settings → Privacy, review the training and logging options. If you need stricter
  handling, pin `OPENROUTER_MODEL` to models whose providers don't retain data, even if that means paid models.
- **Recommended:** name OpenRouter and the model providers as sub-processors in the privacy notice (§6).

## 4. Privacy guardrails

| # | Guardrail | Status |
|---|-----------|--------|
| G1 | No accounts; no names, emails or phone numbers collected (data minimisation) | **Implemented** |
| G2 | Original photo never stored; only a 320 px thumbnail | **Implemented** (`ai.prepare_image`) |
| G3 | EXIF metadata (GPS location, device) stripped before sending or storing | **Implemented** (JPEG re-encode) |
| G4 | Pseudonymous random `client_id`, not linked to identity | **Implemented** |
| G5 | Users see only their own history list; the community view is aggregate numbers only | **Implemented** |
| G6 | Database table protected by RLS; only the server (`service_role` key) can access it | **Implemented** (`supabase/schema.sql`) |
| G7 | Secrets only in environment variables; `.env` git-ignored; nothing secret sent to the browser | **Implemented** |
| G8 | HTTPS in transit (Render and Supabase TLS); Supabase encrypts at rest | **Implemented** (platform) |
| G9 | Photo bytes and secrets never logged | **Implemented** (logs contain model names and status codes only) |
| G10 | Model output treated as untrusted: clamped, truncated and HTML-escaped | **Implemented** |
| G11 | AI use disclosed: the result shows which AI model answered; demo results are labelled | **Implemented** |
| G12 | Notice on the scan page: "Avoid photos showing people or documents" | **Recommended** |
| G13 | Auto-delete scans older than 90 days (Supabase `pg_cron` job, SQL below) | **Recommended** |
| G14 | "Delete my data" button → `DELETE /api/history` for that `client_id` | **Recommended** |
| G15 | Rate limiting on `/api/scan` (e.g. 10 per minute per IP) to stop abuse | **Recommended** |
| G16 | Privacy notice page (what is collected, why, processors, retention, contact) | **Recommended** |

Retention job (G13), to run in the Supabase SQL editor once `pg_cron` is enabled:
```sql
select cron.schedule('ecoscan-retention', '0 3 * * *',
  $$ delete from public.scans where created_at < now() - interval '90 days' $$);
```

## 5. Regulatory mapping

### 5.1 GDPR (EU / UK GDPR)
| Principle / right | How EcoScan addresses it |
|-------------------|--------------------------|
| Lawful basis | Legitimate interest or consent: the user uploads a photo to get recycling advice. **Recommended:** a short consent line next to the upload button |
| Data minimisation (Art. 5(1)(c)) | G1–G4: no identity data, thumbnail only, EXIF stripped |
| Storage limitation (Art. 5(1)(e)) | **Recommended:** G13, 90-day retention |
| Transparency (Art. 13) | **Recommended:** G16 privacy notice listing OpenRouter and model providers |
| Right to erasure (Art. 17) | **Recommended:** G14. Until then, delete manually by `client_id` in Supabase |
| Security (Art. 32) | G6–G9 |
| International transfers | OpenRouter, model providers and Render may process data outside the EU. **Recommended:** check each processor's safeguards (for example, SCCs) |

### 5.2 India: Digital Personal Data Protection Act 2023 (regional standard)
- Notice and consent before processing: G12 + G16 + a consent line (**Recommended**).
- Purpose limitation: data is used only to produce recycling advice and impact stats. There is no advertising and no profiling.
- Erasure on request and on purpose completion: G13 and G14 (**Recommended**).
- Reasonable security safeguards: G6–G9 (**Implemented**).

### 5.3 EU AI Act
- **Risk category: minimal/limited risk.** Classifying waste items for recycling advice is not a
  high-risk use under Annex III. It makes no decisions about people's access to jobs, credit, education or services.
- **Transparency:** users are told the results are AI-generated, and which model produced them (G11).
- **Human oversight:** results are advisory. The UI shows confidence and tells users to check local rules.
- No biometric identification, emotion recognition or profiling of people.

## 6. Data subject and user controls (target state)

| Control | v1 | Target |
|---------|----|--------|
| See my data | Dashboard + history | — |
| Delete my data | Clear browser storage (unlinks history); manual deletion by an admin | "Delete my data" button (G14) |
| Opt out of storage | — | "Don't save this scan" toggle |
| Contact | Repository owner | Privacy contact email in G16 |

## 7. Access control and operations

| Role | Access |
|------|--------|
| End user | Own history (by browser), community aggregates, any scan whose unlisted UUID link they have |
| Backend (Render) | Full read/write to `scans` via the `service_role` key |
| Team admins | Supabase dashboard (enable MFA on Supabase, Render and OpenRouter accounts) |

- **Key rotation:** if a key leaks, rotate `SUPABASE_KEY` in Supabase → Settings → API and `OPENROUTER_API_KEY` in OpenRouter, then update Render's env vars and redeploy.
- **Incident response:** (1) rotate keys, (2) review Supabase logs, (3) delete affected rows, (4) notify affected users or the regulator if the law requires it (GDPR: within 72 h).

## 8. Compliance log

Record every change that affects data handling here.

| Date | Change | Data impact | By |
|------|--------|-------------|----|
| 2026-09-30 | v1 launched: scans stored in Supabase with thumbnail, analysis, anonymous `client_id` | New storage of thumbnails and pseudonymous IDs | Team EcoScan |
| 2026-09-30 | EXIF stripping and thumbnail-only storage adopted (ADR-004) | Reduces location and personal data exposure | Team EcoScan |
| | *next: retention job (G13), delete endpoint (G14), privacy notice (G16)* | | |
