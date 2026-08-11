import { AsyncLocalStorage } from 'async_hooks';

interface TenantStore {
  tenantId?: string;
}

// Node's equivalent of the Python fleet's ContextVar-based tenant context
// (see e.g. content-engine/app/tenant_context.py). AsyncLocalStorage.run()
// scopes the store to exactly the callback (and everything it awaits) for
// one request - unlike the Python ContextVar pattern, there's no separate
// "clear" step to forget: a request that never calls .run() with a
// tenantId simply never has one in its async context, so the leak bug
// found and fixed fleet-wide this session (a middleware that set the
// context on requests with a header but never cleared it for requests
// without one) can't happen here by construction.
const tenantStorage = new AsyncLocalStorage<TenantStore>();

export function runWithTenant<T>(tenantId: string | undefined, fn: () => T): T {
  return tenantStorage.run({ tenantId }, fn);
}

export function getTenantId(): string | undefined {
  return tenantStorage.getStore()?.tenantId;
}
