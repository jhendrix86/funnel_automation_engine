import { Request, Response, NextFunction } from 'express';
import { runWithTenant } from './tenantContext';

/**
 * Extracts X-Tenant-ID (same header convention as the rest of the fleet's
 * standalone engines) and scopes the rest of the request's async call
 * chain to it via AsyncLocalStorage. See tenantContext.ts for why this
 * can't leak between requests the way the Python ContextVar-based version
 * could before it was fixed fleet-wide.
 */
export function tenantMiddleware(req: Request, _res: Response, next: NextFunction): void {
  const tenantId = req.header('X-Tenant-ID') || undefined;
  runWithTenant(tenantId, next);
}
