import request from 'supertest';
import { connectTestDb, closeTestDb, clearTestDb } from './mongoTestServer';
import { createApp } from '../src/app';

const app = createApp();

beforeAll(connectTestDb);
afterAll(closeTestDb);
afterEach(clearTestDb);

describe('tenant isolation through the real HTTP API (not just the model layer)', () => {
  test('a created funnel is scoped to the X-Tenant-ID that created it', async () => {
    const createRes = await request(app)
      .post('/api/funnels')
      .set('X-Tenant-ID', 'tenant-a')
      .send({ name: 'Tenant A Funnel' });

    expect(createRes.status).toBe(201);
    expect(createRes.body.tenantId).toBe('tenant-a');

    const listAsA = await request(app).get('/api/funnels').set('X-Tenant-ID', 'tenant-a');
    expect(listAsA.body.funnels).toHaveLength(1);

    const listAsB = await request(app).get('/api/funnels').set('X-Tenant-ID', 'tenant-b');
    expect(listAsB.body.funnels).toHaveLength(0);
  });

  test('tenant B cannot read, update, or delete tenant A\'s funnel by id', async () => {
    const createRes = await request(app)
      .post('/api/funnels')
      .set('X-Tenant-ID', 'tenant-a')
      .send({ name: 'Tenant A Funnel' });
    const funnelId = createRes.body._id;

    const getAsB = await request(app).get(`/api/funnels/${funnelId}`).set('X-Tenant-ID', 'tenant-b');
    expect(getAsB.status).toBe(404);

    const updateAsB = await request(app)
      .put(`/api/funnels/${funnelId}`)
      .set('X-Tenant-ID', 'tenant-b')
      .send({ name: 'hijacked' });
    expect(updateAsB.status).toBe(404);

    const deleteAsB = await request(app).delete(`/api/funnels/${funnelId}`).set('X-Tenant-ID', 'tenant-b');
    expect(deleteAsB.status).toBe(404);

    const getAsA = await request(app).get(`/api/funnels/${funnelId}`).set('X-Tenant-ID', 'tenant-a');
    expect(getAsA.status).toBe(200);
    expect(getAsA.body.name).toBe('Tenant A Funnel');
  });

  test('two tenants can each create a lead with the same email under their own funnel', async () => {
    const funnelA = (
      await request(app).post('/api/funnels').set('X-Tenant-ID', 'tenant-a').send({ name: 'A' })
    ).body;
    const funnelB = (
      await request(app).post('/api/funnels').set('X-Tenant-ID', 'tenant-b').send({ name: 'B' })
    ).body;

    const leadA = await request(app)
      .post('/api/leads')
      .set('X-Tenant-ID', 'tenant-a')
      .send({ email: 'shared@example.com', funnelId: funnelA._id, source: 'test' });
    const leadB = await request(app)
      .post('/api/leads')
      .set('X-Tenant-ID', 'tenant-b')
      .send({ email: 'shared@example.com', funnelId: funnelB._id, source: 'test' });

    expect(leadA.status).toBe(201);
    expect(leadB.status).toBe(201);
    expect(leadA.body.tenantId).toBe('tenant-a');
    expect(leadB.body.tenantId).toBe('tenant-b');

    const leadsAsA = await request(app).get('/api/leads').set('X-Tenant-ID', 'tenant-a');
    expect(leadsAsA.body.leads).toHaveLength(1);
    const leadsAsB = await request(app).get('/api/leads').set('X-Tenant-ID', 'tenant-b');
    expect(leadsAsB.body.leads).toHaveLength(1);
  });

  test('a request with no X-Tenant-ID header sees everything, matching the rest of the fleet', async () => {
    await request(app).post('/api/funnels').set('X-Tenant-ID', 'tenant-a').send({ name: 'A' });
    await request(app).post('/api/funnels').set('X-Tenant-ID', 'tenant-b').send({ name: 'B' });

    const listNoHeader = await request(app).get('/api/funnels');
    expect(listNoHeader.body.funnels).toHaveLength(2);
  });

  test('cache failures (Redis never connected under test) do not break real create/list operations', async () => {
    // Redis is intentionally never connected in this test file - proves
    // cacheSet()'s best-effort fix actually holds under real execution,
    // not just by reading the code.
    const createRes = await request(app)
      .post('/api/funnels')
      .set('X-Tenant-ID', 'tenant-a')
      .send({ name: 'Cache-agnostic funnel' });
    expect(createRes.status).toBe(201);
  });
});
