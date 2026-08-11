import { connectTestDb, closeTestDb, clearTestDb } from './mongoTestServer';
import { runWithTenant as runWithTenantRaw } from '../src/middleware/tenantContext';
import { Funnel } from '../src/models/Funnel';
import { Lead } from '../src/models/Lead';

/**
 * Wraps runWithTenant so `fn` is always awaited *inside* the
 * AsyncLocalStorage-active callback, not by the caller afterwards.
 *
 * Mongoose's find()/findById()/countDocuments() etc. return lazy `Query`
 * objects - unlike a real Promise, nothing happens (no pre-hook fires)
 * until `.then()`/`await` is actually called on them. `runWithTenant('a',
 * () => Funnel.find())` returns that inert Query synchronously; if the
 * *caller* is the one who then awaits it, the query only actually executes
 * after als.run() has already returned, outside the tenant context. The
 * real HTTP path never hits this because a controller's own `await
 * Funnel.find()...` happens synchronously inside the request's still-active
 * runWithTenant(tenantId, next) call (see tenantMiddleware.ts) - this
 * helper reproduces that same shape for direct model-level tests.
 */
function runWithTenant<T>(tenantId: string | undefined, fn: () => T | Promise<T>): Promise<T> {
  return runWithTenantRaw(tenantId, async () => {
    return await fn();
  });
}

beforeAll(connectTestDb);
afterAll(closeTestDb);
afterEach(clearTestDb);

async function makeFunnel(name: string) {
  return Funnel.create({ name, description: 'test' });
}

describe('tenantScoped plugin - real MongoDB behavior, not mocked', () => {
  test('auto-assigns tenantId on create from the current context', async () => {
    const funnel = await runWithTenant('tenant-a', () => makeFunnel('A funnel'));
    expect(funnel.tenantId).toBe('tenant-a');
  });

  test('leaves tenantId unset when there is no tenant context', async () => {
    const funnel = await makeFunnel('No tenant funnel');
    expect(funnel.tenantId).toBeUndefined();
  });

  test('does not overwrite an explicitly-provided tenantId', async () => {
    const funnel = await runWithTenant('tenant-a', () =>
      Funnel.create({ name: 'explicit', tenantId: 'tenant-explicit' })
    );
    expect(funnel.tenantId).toBe('tenant-explicit');
  });

  test('queries under a tenant context only see that tenant\'s data', async () => {
    await runWithTenant('tenant-a', () => makeFunnel('A1'));
    await runWithTenant('tenant-a', () => makeFunnel('A2'));
    await runWithTenant('tenant-b', () => makeFunnel('B1'));

    const aFunnels = await runWithTenant('tenant-a', () => Funnel.find());
    const bFunnels = await runWithTenant('tenant-b', () => Funnel.find());

    expect(aFunnels.map((f) => f.name).sort()).toEqual(['A1', 'A2']);
    expect(bFunnels.map((f) => f.name)).toEqual(['B1']);
  });

  test('a request with no tenant header sees everything (matches the rest of the fleet\'s convention)', async () => {
    await runWithTenant('tenant-a', () => makeFunnel('A1'));
    await runWithTenant('tenant-b', () => makeFunnel('B1'));

    const all = await Funnel.find();
    expect(all.map((f) => f.name).sort()).toEqual(['A1', 'B1']);
  });

  test('findById/findByIdAndUpdate/findByIdAndDelete respect tenant scoping', async () => {
    const aFunnel = await runWithTenant('tenant-a', () => makeFunnel('A1'));

    // Tenant B can't read, update, or delete tenant A's funnel by id.
    const readByB = await runWithTenant('tenant-b', () => Funnel.findById(aFunnel._id));
    expect(readByB).toBeNull();

    const updatedByB = await runWithTenant('tenant-b', () =>
      Funnel.findByIdAndUpdate(aFunnel._id, { name: 'hijacked' }, { new: true })
    );
    expect(updatedByB).toBeNull();

    const deletedByB = await runWithTenant('tenant-b', () => Funnel.findByIdAndDelete(aFunnel._id));
    expect(deletedByB).toBeNull();

    // Tenant A still has it, unmodified.
    const stillThere = await runWithTenant('tenant-a', () => Funnel.findById(aFunnel._id));
    expect(stillThere?.name).toBe('A1');
  });

  test('countDocuments respects tenant scoping', async () => {
    await runWithTenant('tenant-a', () => makeFunnel('A1'));
    await runWithTenant('tenant-a', () => makeFunnel('A2'));
    await runWithTenant('tenant-b', () => makeFunnel('B1'));

    expect(await runWithTenant('tenant-a', () => Funnel.countDocuments())).toBe(2);
    expect(await runWithTenant('tenant-b', () => Funnel.countDocuments())).toBe(1);
  });

  test('two different tenants can each have a lead with the same email', async () => {
    const funnelA = await runWithTenant('tenant-a', () => makeFunnel('A1'));
    const funnelB = await runWithTenant('tenant-b', () => makeFunnel('B1'));

    const leadA = await runWithTenant('tenant-a', () =>
      Lead.create({ email: 'same@example.com', funnelId: funnelA._id })
    );
    const leadB = await runWithTenant('tenant-b', () =>
      Lead.create({ email: 'same@example.com', funnelId: funnelB._id })
    );

    expect(leadA.tenantId).toBe('tenant-a');
    expect(leadB.tenantId).toBe('tenant-b');

    // The same email is still unique WITHIN a tenant.
    await expect(
      runWithTenant('tenant-a', () => Lead.create({ email: 'same@example.com', funnelId: funnelA._id }))
    ).rejects.toThrow();
  });
});
