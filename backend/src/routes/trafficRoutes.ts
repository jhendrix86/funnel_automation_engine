import { Router } from 'express';
import { TrafficController } from '../controllers/TrafficController';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();
const trafficController = new TrafficController();

// Track traffic
router.post('/track', asyncHandler(trafficController.trackTraffic));

// Get traffic analytics
router.get('/analytics', asyncHandler(trafficController.getTrafficAnalytics));

// Get traffic sources breakdown
router.get('/sources', asyncHandler(trafficController.getTrafficSources));

// Optimize traffic allocation
router.post('/optimize', asyncHandler(trafficController.optimizeTrafficAllocation));

export { router as trafficRoutes };