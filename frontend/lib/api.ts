/**
 * Single source of truth for backend base URLs.
 *
 * Set these at build/run time to point the app at a real backend:
 *   NEXT_PUBLIC_API_URL         - the funnel API. Backend of record is the
 *                                 Python orchestrator
 *                                 (python-services/orchestrator.py),
 *                                 host-mapped to :18000 in docker-compose.
 *   NEXT_PUBLIC_EMPIRE_API_URL  - the empire_os engine API (:8100)
 *
 * Defaults target the local docker-compose host ports so behaviour is
 * sane when the vars are unset (local dev).
 *
 * Backend of record (settled 2026-09-03, user pick — see
 * BACKEND_OF_RECORD.md): the funnel call sites (`/funnels`,
 * `/funnel/create`, `/funnel/:id/launch|pause|resume`, `DELETE /funnel/:id`,
 * `/analytics/:id`) are an exact match for the orchestrator's routes. The
 * Node Express `backend/` (:3001) is NON-CANONICAL and nothing consumes it
 * (see backend/NONCANONICAL.md). Earlier "every funnel call 404s" was just
 * this default pointing at :8000, which on the fleet host is
 * baselayer-backend-dev, a different FastAPI app.
 */

const stripTrailingSlash = (u: string) => u.replace(/\/+$/, '')

export const API_BASE = stripTrailingSlash(
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18000'
)

export const EMPIRE_API_BASE = stripTrailingSlash(
  process.env.NEXT_PUBLIC_EMPIRE_API_URL || 'http://localhost:8100'
)
