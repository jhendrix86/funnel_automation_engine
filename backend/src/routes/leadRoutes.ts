import { Router } from 'express';
import { LeadController } from '../controllers/LeadController';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();
const leadController = new LeadController();

// Create lead
router.post('/', asyncHandler(leadController.createLead));

// Get all leads
router.get('/', asyncHandler(leadController.getLeads));

// Get lead by ID
router.get('/:id', asyncHandler(leadController.getLead));

// Update lead
router.put('/:id', asyncHandler(leadController.updateLead));

// Delete lead
router.delete('/:id', asyncHandler(leadController.deleteLead));

// Track lead behavior
router.post('/:id/behavior', asyncHandler(leadController.trackBehavior));

// Update lead score
router.post('/:id/score', asyncHandler(leadController.updateScore));

// Get leads by funnel
router.get('/funnel/:funnelId', asyncHandler(leadController.getLeadsByFunnel));

// Segment leads
router.post('/segment', asyncHandler(leadController.segmentLeads));

export { router as leadRoutes };