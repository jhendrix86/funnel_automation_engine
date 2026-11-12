// Server-side proxy for the funnel dashboard.
//
// Why this exists: the dashboard components used to call the orchestrator
// directly from the browser (http://localhost:8000/...). After the H-02
// hardening, every orchestrator route except /health requires an X-API-Key
// header, so those browser calls answer 401. The key must never reach the
// browser, so the browser now calls this route instead, and this route
// (server-only) attaches the key and forwards the request.
//
// The browser never sees FUNNEL_API_KEY. The orchestrator stays
// loopback-only. Nothing here changes the H-02 protections.
//
// Configuration (server environment only, never committed):
//   FUNNEL_API_KEY   - required; without it this route answers 503, never 401
//                      passthrough, and never forwards unauthenticated.
//   ORCHESTRATOR_URL - optional; defaults to http://localhost:8000
//                      (the loopback address the services bind to).
//
// Forwarded: method, query string, JSON body, and Content-Type.
// Never forwarded: any client-supplied X-API-Key or Authorization header
// (the server key is the only credential sent upstream).

const ORCHESTRATOR_URL =
  process.env.ORCHESTRATOR_URL ?? 'http://localhost:8000';

async function proxy(request: Request, path: string[]) {
  const apiKey = process.env.FUNNEL_API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({
        error:
          'Funnel API key is not configured on the server. Set FUNNEL_API_KEY before using the dashboard.',
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const url = new URL(request.url);
  const target = `${ORCHESTRATOR_URL.replace(/\/$/, '')}/${path.join('/')}${url.search}`;

  const headers = new Headers();
  headers.set('X-API-Key', apiKey);
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, { method: request.method, headers, body });
  } catch (error) {
    return new Response(
      JSON.stringify({
        error: 'Orchestrator is unreachable from the server.',
        detail: error instanceof Error ? error.message : 'unknown error',
      }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: {
      'Content-Type':
        upstream.headers.get('content-type') ?? 'application/json',
    },
  });
}

type RouteContext = { params: { path: string[] } };

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, context.params.path);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, context.params.path);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, context.params.path);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context.params.path);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context.params.path);
}
