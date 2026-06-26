import { Router } from 'express';
import { AnalyticsController } from '../controllers/AnalyticsController';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();
const analyticsController = new AnalyticsController();

// Get comprehensive analytics
router.get('/dashboard', asyncHandler(analyticsController.getDashboardAnalytics));

// Get funnel performance
router.get('/funnel/:funnelId', asyncHandler(analyticsController.getFunnelPerformance));

// Get conversion trends
router.get('/conversions', asyncHandler(analyticsController.getConversionTrends));

// Get lead quality metrics
router.get('/lead-quality', asyncHandler(analyticsController.getLeadQualityMetrics));

// Get traffic source ROI
router.get('/traffic-roi', asyncHandler(analyticsController.getTrafficSourceROI));

// Get real-time analytics
router.get('/realtime', asyncHandler(analyticsController.getRealTimeAnalytics));

// Generate performance report
router.post('/report', asyncHandler(analyticsController.generatePerformanceReport));

export { router as analyticsRoutes };