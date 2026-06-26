import { Router } from 'express';
import { FunnelController } from '../controllers/FunnelController';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();
const funnelController = new FunnelController();

// Create funnel
router.post('/', asyncHandler(funnelController.createFunnel));

// Get all funnels
router.get('/', asyncHandler(funnelController.getFunnels));

// Get funnel by ID
router.get('/:id', asyncHandler(funnelController.getFunnel));

// Update funnel
router.put('/:id', asyncHandler(funnelController.updateFunnel));

// Delete funnel
router.delete('/:id', asyncHandler(funnelController.deleteFunnel));

// Activate/deactivate funnel
router.patch('/:id/status', asyncHandler(funnelController.updateFunnelStatus));

// Get funnel analytics
router.get('/:id/analytics', asyncHandler(funnelController.getFunnelAnalytics));

// Update funnel settings
router.patch('/:id/settings', asyncHandler(funnelController.updateFunnelSettings));

// Add traffic source
router.post('/:id/traffic-sources', asyncHandler(funnelController.addTrafficSource));

// Add landing page
router.post('/:id/landing-pages', asyncHandler(funnelController.addLandingPage));

// Add lead magnet
router.post('/:id/lead-magnets', asyncHandler(funnelController.addLeadMagnet));

// Add email sequence
router.post('/:id/email-sequences', asyncHandler(funnelController.addEmailSequence));

export { router as funnelRoutes };