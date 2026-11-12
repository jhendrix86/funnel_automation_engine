/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // No rewrites: /api/funnel/* is served by the server-side route handler
  // in app/api/funnel/[...path]/route.ts, which attaches the server-side
  // FUNNEL_API_KEY. The previous /api -> orchestrator rewrite is removed
  // because it forwarded browser requests to the orchestrator without the
  // key, which the H-02 hardening now rejects with 401.
}

module.exports = nextConfig
