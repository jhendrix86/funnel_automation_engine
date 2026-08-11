import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { errorHandler } from './middleware/errorHandler';
import { tenantMiddleware } from './middleware/tenantMiddleware';
import { trafficRoutes } from './routes/trafficRoutes';
import { leadRoutes } from './routes/leadRoutes';
import { funnelRoutes } from './routes/funnelRoutes';
import { analyticsRoutes } from './routes/analyticsRoutes';

/**
 * Express app construction only - no Redis/Mongo connection, no
 * httpServer.listen(). Split out of index.ts so tests can import and
 * exercise real routes (via supertest) against a real in-memory MongoDB
 * without needing a live Redis or an actual listening port.
 */
export function createApp() {
  const app = express();

  // Rate limiting for DDoS protection
  const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10000, // Limit each IP to 10000 requests per windowMs
    message: 'Too many requests from this IP, please try again later.'
  });

  app.use(helmet());
  app.use(cors());
  app.use(compression());
  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true, limit: '10mb' }));
  app.use(limiter);
  app.use(tenantMiddleware);

  app.get('/health', (_req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
  });

  app.use('/api/traffic', trafficRoutes);
  app.use('/api/leads', leadRoutes);
  app.use('/api/funnels', funnelRoutes);
  app.use('/api/analytics', analyticsRoutes);

  app.use(errorHandler);

  return app;
}
