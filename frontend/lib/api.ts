/**
 * Single source of truth for backend base URLs.
 *
 * Set these at build/run time to point the app at a real backend:
 *   NEXT_PUBLIC_API_URL         - the funnel API (Express backend, :3001 in
 *                                 docker-compose; the python orchestrator is
 *                                 :18000 on the host - see note below)
 *   NEXT_PUBLIC_EMPIRE_API_URL  - the empire_os engine API (:8100)
 *
 * Defaults match the repo's historical hardcoded values so behaviour is
 * unchanged when the vars are unset (local dev).
 *
 * NOTE (2026-09-02): the funnel call sites still use the OLD path shape
 * (`/funnels`, `/funnel/create`, `/funnel/:id/launch|pause|resume`,
 * `/analytics/:id`). The live Express backend serves `/api/funnels`,
 * `POST /api/funnels`, `PATCH /api/funnels/:id/status`,
 * `GET /api/analytics/funnel/:id`. Converging the base URL (this file) does
 * NOT fix that path/verb mismatch - see OS42_ROADMAP.md step 10 / HANDOFF.md.
 */

const stripTrailingSlash = (u: string) => u.replace(/\/+$/, '')

export const API_BASE = stripTrailingSlash(
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
)

export const EMPIRE_API_BASE = stripTrailingSlash(
  process.env.NEXT_PUBLIC_EMPIRE_API_URL || 'http://localhost:8100'
)
