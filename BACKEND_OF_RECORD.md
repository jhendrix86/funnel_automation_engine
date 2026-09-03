# Funnel Automation Engine — backend-of-record decision

**Status:** research complete, awaiting user pick (A or B).
**Date:** 2026-09-03 (Nexus).
**Context:** `OS42_ROADMAP.md` step 10 follow-up 1 — the frontend's funnel-data
calls 404, and it was unclear whether the **Express** backend (`backend/`,
host `:3001`) or the **Python orchestrator** (`python-services/orchestrator.py`,
host `:18000`) is canonical. This doc settles it.

---

## TL;DR

**The Python orchestrator (`:18000`) is the de-facto backend of record.** The
frontend was written against it, `docker-compose.yml` already wires the
frontend to it, the README documents only it, and `next.config.js`'s rewrite
targets it. The Express `backend/` is an orphan scaffold that **nothing
consumes** — no frontend call site, no other service.

The "every funnel call 404s" symptom is **not** a deep contract mismatch
against the intended backend. It has one real cause: **`frontend/lib/api.ts`
defaults `API_BASE` to `http://localhost:8000`, and on the fleet host
`:8000` is `baselayer-backend-dev`** (a different FastAPI app), which answers
every unknown path with `{"detail":"Not Found"}` (HTTP 404). Point the
frontend at `:18000` and the calls resolve.

**Recommended: Option A.** ~15–30 min, no code logic changes, just base-URL
config + marking `backend/` non-canonical.

---

## Evidence

### 1. Endpoint maps

#### Frontend call sites (all 9, post-`8309ffc` — converged onto `lib/api.ts`)

| Call site | Method + path (relative to `API_BASE`) | Request body | Response used |
|---|---|---|---|
| `app/page.tsx:37` | `GET /funnels` | — | `data.funnels` |
| `components/CreateFunnelModal.tsx:63` | `POST /funnel/create` | `{name, target_audience:{description}, goals:[...], auto_launch, create_product?, product_name?, product_description?, product_price?, product_tags?, gumroad_product_id?}` | `response.ok` only |
| `components/FunnelDashboard.tsx:36` | `POST /funnel/:id/launch` | `{launch_traffic, launch_email_campaign, launch_seo}` | `response.ok` |
| `components/FunnelDashboard.tsx:58` | `POST /funnel/:id/pause` | — | `response.ok` |
| `components/FunnelDashboard.tsx:74` | `POST /funnel/:id/resume` | — | `response.ok` |
| `components/FunnelDashboard.tsx:93` | `DELETE /funnel/:id` | — | `response.ok` |
| `app/analytics/[funnelId]/page.tsx:45` | `GET /analytics/:id` | — | whole JSON blob |
| `app/mission-control/page.tsx:92,121` | `POST /funnel/create`, `GET /funnels` | as above | `funnel_id` / `funnels` |
| `app/system/page.tsx` + `mission-control` | `EMPIRE_API_BASE` → `/engines*`, `/health` | — | empire_os, **separate concern** |

#### Python orchestrator — `python-services/orchestrator.py` (FastAPI, container `:8000`, host `:18000`)

| Route | Matches frontend? | Notes |
|---|---|---|
| `GET /funnels` (`?status=`) → `{"funnels":[...]}` | ✅ exact | line 819 |
| `POST /funnel/create` → `{funnel_id, workflow_id, product_id, status, message, components}` | ✅ exact | line 149; body model `FunnelCreationRequest` (l.103) **matches the frontend payload field-for-field** |
| `POST /funnel/{id}/launch` → `{funnel_id, status, tasks_completed}` | ✅ exact | line 485; body model `FunnelLaunchRequest` (l.124) **matches** `{launch_traffic, launch_email_campaign, launch_seo}` |
| `POST /funnel/{id}/pause` → `{status:"paused"}` | ✅ exact | line 911 |
| `POST /funnel/{id}/resume` → `{status:"active"}` | ✅ exact | line 927 |
| `DELETE /funnel/{id}` → `{status:"deleted"}` | ✅ exact | line 888 |
| `GET /analytics/{id}` → rich `{funnel, analytics, gumroad, traffic, leads, email}` | ✅ exact | line 846 |
| `GET /funnel/{id}` → `{funnel, workflows, traffic_campaigns}` | ✅ exact | line 829 |
| `POST /workflow/create`, `POST /workflow/{id}/execute` | (no frontend caller) | l.736, 762 |

**7 / 7 frontend funnel paths resolve to a real orchestrator route.**

#### Express — `backend/src/` (Express + Mongoose + Socket.IO, host `:3001`)

Mounted (`backend/src/app.ts`): `/api/traffic`, `/api/leads`, `/api/funnels`,
`/api/analytics`, plus `GET /health`.

| Express funnel route (`funnelRoutes.ts`) | Frontend equivalent? |
|---|---|
| `POST /api/funnels` | frontend calls `POST /funnel/create` — ❌ |
| `GET /api/funnels` → `{funnels, pagination}` | frontend calls `GET /funnels`, reads `.funnels` — ❌ path, ✅ shape-ish |
| `GET /api/funnels/:id` | frontend calls `GET /funnel/:id` — ❌ |
| `PUT /api/funnels/:id` | (no frontend caller) |
| `DELETE /api/funnels/:id` | frontend calls `DELETE /funnel/:id` — ❌ |
| `PATCH /api/funnels/:id/status` (body `{status}`) | frontend calls `POST /funnel/:id/{pause,resume}` — ❌ verb + path + shape |
| `GET /api/funnels/:id/analytics` | frontend calls `GET /analytics/:id` — ❌ |
| `PATCH /api/funnels/:id/settings`, `POST /api/funnels/:id/{traffic-sources,landing-pages,lead-magnets,email-sequences}` | (no frontend caller) |
| **No `launch` / `resume` route at all** | frontend calls `POST /funnel/:id/launch` — ❌ |
| Requires `X-Tenant-ID` header (`tenantMiddleware`) | frontend sends none — ❌ |

**0 / 7 frontend funnel paths resolve on Express.**

### 2. Live probe (Nexus, 2026-09-03, fleet up)

```
# frontend's exact paths -> orchestrator :18000
GET    /funnels                       -> 200   {"funnels":[]}
POST   /funnel/create                 -> 422   (route exists; body validation on empty {})
POST   /funnel/<oid>/launch           -> 404   (route exists; "Funnel not found" — no such funnel)
POST   /funnel/<oid>/pause            -> 200
POST   /funnel/<oid>/resume           -> 200
DELETE /funnel/<oid>                  -> 200
GET    /analytics/<oid>               -> 404   (route exists; "Funnel not found")

# same paths -> Express :3001
GET /funnels, POST /funnel/create, POST /funnel/<oid>/launch,
DELETE /funnel/<oid>, GET /analytics/<oid>   -> 404 (Cannot <M> <path>) for every one

# what actually answers on host :8000 (the lib/api.ts default)
GET http://localhost:8000/            -> {"name":"BaseLayer API",...}   <-- baselayer-backend-dev
GET http://localhost:8000/funnels     -> {"detail":"Not Found"}  (FastAPI 404)
```

`docker ps`: `traffic-funnel-orchestrator` = `0.0.0.0:18000->8000`,
`traffic-funnel-backend` = `0.0.0.0:3001->3001`, `baselayer-backend-dev` =
`0.0.0.0:8000->8000`.

### 3. Design-intent signals (all point to the orchestrator)

- **`docker-compose.yml`** — the `frontend` service sets
  `NEXT_PUBLIC_API_URL=http://localhost:18000` and `depends_on: orchestrator`.
  It does **not** depend on `backend`. (Host port `:8000`→`:18000` was
  remapped 2026-08-14 to dodge exactly the baselayer collision above; see the
  `cab4bde` commit and `OS42_ROADMAP.md` step 2.)
- **`README.md`** — "Architecture" lists `python-services/` as *"Backend
  microservices"* and `orchestrator.py` as *"Central coordination service"*.
  The Node `backend/` is **not mentioned anywhere** in the README.
- **`docker-compose.yml` comment (l.286-289)** on the `backend` service:
  *"was dead, uncommitted scaffold with no models until this session … Was
  never listed here before because it was never a live service."*
- **`next.config.js`** rewrite `/api/:path*` → `${NEXT_PUBLIC_API_URL}/:path*`
  **strips the `/api` prefix** — i.e. it expects a backend whose routes are
  bare (`/funnels`), which is the orchestrator, not Express (`/api/funnels`).
- **Payload models match.** `CreateFunnelModal`'s body is a field-for-field
  match for `FunnelCreationRequest`; `handleLaunch`'s body matches
  `FunnelLaunchRequest`. The frontend was coded against these Pydantic models.
- **The two backends don't even share a database.** Orchestrator →
  `mongo_client.traffic_funnel` (underscore, auto-created on first write —
  currently absent). Express → `mongodb://mongodb:27017/traffic-funnel`
  (hyphen — exists, holds `funnels`/`leads`, populated only by Express's own
  tenant tests). They have never shared funnel state.

### 4. What HP-15 saw (roadmap step 10 follow-up 1)

HP-15's live-wiring pass verified connectivity against **Express `:3001`**
and concluded *"paths look Express"*. That's the wrong read: the frontend
paths are `/funnels`, `/funnel/create`, `/funnel/:id/launch` — none of which
are Express's `/api/...` shape. They are an exact match for the orchestrator.
HP-15's proxy check (`GET /api/funnels` → *"real Express 404 `Cannot GET
/funnels`"*) was reaching Express via the rewrite; against the orchestrator
that same relative call would 200.

---

## Option A — Python orchestrator (`:18000`) is the backend of record  ⭐ recommended

**Rationale:** it's what the frontend already targets, what compose already
wires, and the only backend that implements funnel *orchestration* (launch
fans out to 7 Python microservices — traffic, email, SEO, continuous
optimization loop; Express has none of that). Zero frontend logic changes.

### Changes (losing side = Express `backend/`, which is simply demoted)

| # | File | Change | Effort |
|---|---|---|---|
| 1 | `frontend/lib/api.ts` | `API_BASE` default `http://localhost:8000` → `http://localhost:18000`; rewrite the stale NOTE comment (the path-mismatch warning no longer applies to the orchestrator) | 2 lines |
| 2 | `frontend/next.config.js` | rewrite fallback `'http://localhost:8000'` → `'http://localhost:18000'` | 1 line |
| 3 | `frontend/.env`, `frontend/.env.example` (and root `.env*`) | `NEXT_PUBLIC_API_URL=http://localhost:18000` | 1 line each |
| 4 | `docker-compose.yml` | **already correct** (`:18000`) — no change | — |
| 5 | `backend/README.md` (new) or a header comment in `backend/src/app.ts` + a `docker-compose.yml` note | Mark Express `backend/` **NON-CANONICAL** — retained for its Stage 4 tenant-isolation model + 39 tests, not on the frontend's path. Keeps the next person from re-deriving this. | ~10 min |
| 6 | *(optional, non-blocking)* `orchestrator.py` | `pause`/`resume`/`delete` do an unconditional `update_one` with no existence check → 200 on a missing funnel. `launch` and `analytics` already 404 correctly. Frontend only checks `response.ok`, so this is cosmetic. | ~15 min if done |

**Verification:** `npm run build`; run the stack; from the browser origin
confirm `GET /funnels` → 200, `POST /funnel/create` (real Gumroad id) → 201,
`POST /funnel/:id/pause` → 200, analytics page loads. (Route existence
already confirmed by the probe above.)

**Total: ~15–30 min** (items 1–5). No new endpoints, no frontend path edits.

### Trade-offs
- Express's Stage-4 MongoDB multi-tenancy work (`tenantPlugin.ts`,
  `X-Tenant-ID` isolation, cross-tenant tests) goes **dormant** — the
  orchestrator has **no tenant isolation** (writes raw dicts, no `tenant_id`).
  If funnel multi-tenancy is a near-term requirement, that work has to be
  ported into the orchestrator later (separate effort, ~1 session). Flag, not
  a blocker — nothing consumes the Express tenancy today.
- Real-time analytics via Socket.IO lives only in Express (`socketService.ts`).
  No frontend code subscribes to it, so nothing is lost today.

---

## Option B — Express (`:3001`) is the backend of record

**Rationale:** keeps the Mongoose schema + tenant isolation + Socket.IO as
the foundation. But the frontend and the orchestration layer both have to be
rebuilt against it.

### Changes

| # | Area | Change | Effort |
|---|---|---|---|
| 1 | `backend/src/routes/funnelRoutes.ts` + controller | Add `POST /api/funnels/:id/launch`, `/pause`, `/resume`. **`launch` is the hard part** — in the orchestrator it fans out to 7 Python services (`traffic-acquisition`, `email-automation`, `content-generator`, SEO, `run_continuous_optimization` loop). Express would either (a) HTTP-proxy to the orchestrator (pointless indirection — then the orchestrator is still the real backend), or (b) reimplement that fan-out in Node. | (b) ≈ 1 day |
| 2 | All 9 frontend call sites | Rewrite paths + verbs: `/funnels`→`/api/funnels`; `/funnel/create`→`POST /api/funnels`; `/funnel/:id/pause`→`PATCH /api/funnels/:id/status` body `{status:'paused'}`; `/funnel/:id/launch`→ new route; `/analytics/:id`→`/api/analytics/funnel/:id` (or `/api/funnels/:id/analytics`); `DELETE /funnel/:id`→`/api/funnels/:id`. Add an `X-Tenant-ID` header to every request (pick where the tenant id comes from — currently the frontend has no auth/tenant concept). | ~3–4 h |
| 3 | Response-shape reconciliation | `POST` create returns a raw Mongoose doc, frontend expects `{funnel_id}`. `GET /api/funnels` returns `{funnels, pagination}`. `updateFunnelStatus` returns the funnel, frontend expects `{status}`. Adjust frontend readers or Express responders. | ~2 h |
| 4 | Data model | Orchestrator writes free-form dicts; Express enforces the `Funnel` Mongoose schema (`backend/src/models/Funnel.ts`). Any funnel created by the Python services would fail Express validation on read. Would need the Python `python-services/*` to write schema-compatible docs, or a migration/adapter. | ~half day, or ongoing risk |
| 5 | `docker-compose.yml` | Point frontend `NEXT_PUBLIC_API_URL` → `:3001`; decide whether the orchestrator + its 7 sub-services stay (they still do the actual traffic/email/content work — Express doesn't replace them, so they'd need to be reachable *some* way). | ~30 min + design |
| 6 | `next.config.js` | rewrite must **keep** `/api` (Express is `/api/*`-prefixed) — change `destination` to not strip it | 1 line |

**Total: ~1–2 days**, and it leaves the orchestrator + 7 Python services
still running the real automation work behind Express — so Express becomes a
CRUD/tenant gateway in front of the orchestrator rather than a true
replacement. Only worth it if tenant isolation on funnel CRUD is a hard
near-term requirement.

### Trade-offs
- Real multi-tenant funnel isolation from day one.
- Socket.IO real-time analytics available (still needs a frontend consumer).
- Large surface area; touches frontend, backend, and the Python services'
  write format. Higher regression risk.
- Does **not** eliminate the orchestrator — the automation fan-out still
  lives there.

---

## Recommendation

**Option A.** The mismatch is a one-line default-URL bug amplified by a
host-port collision with `baselayer` (`:8000`), not a genuine architecture
fork. The orchestrator is already the backend of record in every artifact
that matters (frontend code, compose, README, rewrite config). Do items 1–5,
verify, and explicitly mark `backend/` non-canonical so this doesn't get
re-litigated. Revisit funnel multi-tenancy as its own scoped task if/when
it's actually needed.
