# `backend/` is NOT the backend of record

**Backend of record: [`../python-services/orchestrator.py`](../python-services/orchestrator.py)** (FastAPI, host `:18000`).

Settled 2026-09-03 by the user after a research pass — see
[`../BACKEND_OF_RECORD.md`](../BACKEND_OF_RECORD.md) for the full evidence.

## Why

- The frontend (`frontend/`) is coded against the orchestrator's routes
  (`GET /funnels`, `POST /funnel/create`, `POST /funnel/:id/{launch,pause,resume}`,
  `DELETE /funnel/:id`, `GET /analytics/:id`) — 7/7 map to real orchestrator
  endpoints; 0/7 exist on this Express service (which is `/api/funnels`,
  `PATCH /api/funnels/:id/status`, …).
- `docker-compose.yml` wires the `frontend` service to the orchestrator
  (`NEXT_PUBLIC_API_URL=http://localhost:18000`, `depends_on: orchestrator`).
  Nothing depends on `backend`.
- `README.md` documents `python-services/` as the backend; this service is
  not mentioned.
- Only the orchestrator implements funnel *orchestration* — launch fans out
  to 7 Python microservices (traffic, email, SEO, continuous optimization).
  Express has none of that.

## What this service still is

A retained scaffold. It has a real Mongoose schema, `X-Tenant-ID` tenant
isolation (`src/models/tenantPlugin.ts`) and ~39 passing tests from the
Stage 4 multi-tenancy work. Nothing consumes it today. Keep it for that
tenancy model if/when funnel multi-tenancy becomes a real requirement — at
which point that work would be ported into the orchestrator (the
orchestrator currently has no tenant isolation). **Do not delete it**, but
do not build new frontend or service integration against it.
