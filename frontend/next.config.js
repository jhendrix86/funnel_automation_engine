/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    // Kept for anything that calls a relative /api/* path. Target follows
    // NEXT_PUBLIC_API_URL so it can't drift from the direct-fetch base URL
    // in lib/api.ts. (Most call sites currently use absolute URLs and skip
    // this rewrite - see OS42_ROADMAP.md step 10.)
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
    return [
      {
        source: '/api/:path*',
        destination: `${apiBase}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
