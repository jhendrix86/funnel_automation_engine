import { Request, Response } from 'express';
import { Funnel } from '../models/Funnel';
import { Lead } from '../models/Lead';
import { AppError } from '../middleware/errorHandler';
import { cacheSet, cacheGet } from '../services/redisService';
import { logger } from '../utils/logger';
import { io } from '../index';

export class TrafficController {
  async trackTraffic(req: Request, res: Response) {
    const { funnelId, sessionId, url, referrer, userAgent, utm } = req.body;
    
    // Find the funnel
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Update funnel analytics
    funnel.analytics.visitors += 1;
    
    // Update traffic breakdown
    const source = this.identifyTrafficSource(referrer, utm);
    funnel.analytics.trafficBreakdown[source] = (funnel.analytics.trafficBreakdown[source] || 0) + 1;
    
    // Update daily stats
    const today = new Date().toISOString().split('T')[0];
    const dailyStat = funnel.analytics.dailyStats.find(
      stat => stat.date.toISOString().split('T')[0] === today
    );
    
    if (dailyStat) {
      dailyStat.visitors += 1;
    } else {
      funnel.analytics.dailyStats.push({
        date: new Date(),
        visitors: 1,
        leads: 0,
        conversions: 0,
        revenue: 0
      });
    }
    
    await funnel.save();
    
    // Cache updated analytics
    await cacheSet(`funnel:${funnelId}:analytics`, funnel.analytics);
    
    // Emit real-time update
    io.to(`funnel-${funnelId}`).emit('traffic-update', {
      visitors: funnel.analytics.visitors,
      source: source,
      timestamp: new Date()
    });
    
    logger.info(`Traffic tracked for funnel ${funnelId} from ${source}`);
    res.json({ success: true, source });
  }

  async getTrafficAnalytics(req: Request, res: Response) {
    const { funnelId, startDate, endDate } = req.query;
    
    if (!funnelId) {
      throw new AppError('Funnel ID is required', 400);
    }
    
    // Try cache first
    const cached = await cacheGet(`funnel:${funnelId}:analytics`);
    if (cached) {
      return res.json(cached);
    }
    
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    let analytics = funnel.analytics;
    
    // Filter by date range if provided
    if (startDate || endDate) {
      const start = startDate ? new Date(startDate as string) : new Date(0);
      const end = endDate ? new Date(endDate as string) : new Date();
      
      analytics.dailyStats = funnel.analytics.dailyStats.filter(
        stat => stat.date >= start && stat.date <= end
      );
      
      // Recalculate totals
      analytics.visitors = analytics.dailyStats.reduce((sum, stat) => sum + stat.visitors, 0);
      analytics.leads = analytics.dailyStats.reduce((sum, stat) => sum + stat.leads, 0);
      analytics.conversions = analytics.dailyStats.reduce((sum, stat) => sum + stat.conversions, 0);
      analytics.revenue = analytics.dailyStats.reduce((sum, stat) => sum + stat.revenue, 0);
    }
    
    // Cache the result
    await cacheSet(`funnel:${funnelId}:analytics`, analytics, 300); // 5 minutes
    
    res.json(analytics);
  }

  async getTrafficSources(req: Request, res: Response) {
    const { funnelId } = req.query;
    
    if (!funnelId) {
      throw new AppError('Funnel ID is required', 400);
    }
    
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Analyze traffic source performance
    const sourcePerformance = await this.analyzeSourcePerformance(funnelId);
    
    res.json({
      total: funnel.analytics.visitors,
      breakdown: funnel.analytics.trafficBreakdown,
      performance: sourcePerformance
    });
  }

  async optimizeTrafficAllocation(req: Request, res: Response) {
    const { funnelId } = req.body;
    
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Get performance data for each source
    const sourcePerformance = await this.analyzeSourcePerformance(funnelId);
    
    // Calculate optimal allocation based on conversion rates
    const totalConversionRate = Object.values(sourcePerformance).reduce(
      (sum: number, perf: any) => sum + perf.conversionRate, 0
    );
    
    const optimizedAllocation: Record<string, number> = {};
    
    Object.entries(sourcePerformance).forEach(([source, perf]: [string, any]) => {
      if (totalConversionRate > 0) {
        optimizedAllocation[source] = (perf.conversionRate / totalConversionRate) * 100;
      } else {
        optimizedAllocation[source] = 100 / Object.keys(sourcePerformance).length;
      }
    });
    
    // Update funnel traffic source priorities
    funnel.trafficSources.forEach(source => {
      const performance = sourcePerformance[source.type] || { conversionRate: 0 };
      source.priority = Math.round(performance.conversionRate * 100);
    });
    
    await funnel.save();
    
    logger.info(`Traffic allocation optimized for funnel ${funnelId}`);
    res.json({
      optimizedAllocation,
      sourcePerformance,
      updatedPriorities: funnel.trafficSources
    });
  }

  private identifyTrafficSource(referrer: string, utm: any): string {
    if (utm?.utm_source) {
      return utm.utm_source;
    }
    
    if (referrer) {
      if (referrer.includes('google')) return 'google';
      if (referrer.includes('facebook')) return 'facebook';
      if (referrer.includes('twitter')) return 'twitter';
      if (referrer.includes('linkedin')) return 'linkedin';
      if (referrer.includes('youtube')) return 'youtube';
      return 'referral';
    }
    
    return 'direct';
  }

  private async analyzeSourcePerformance(funnelId: string) {
    const leads = await Lead.find({ funnelId });
    
    const sourcePerformance: Record<string, any> = {};
    
    leads.forEach(lead => {
      const source = lead.source;
      if (!sourcePerformance[source]) {
        sourcePerformance[source] = {
          visitors: 0,
          leads: 0,
          conversions: 0,
          conversionRate: 0
        };
      }
      
      sourcePerformance[source].leads += 1;
      if (lead.status === 'converted') {
        sourcePerformance[source].conversions += 1;
      }
    });
    
    // Calculate conversion rates
    Object.keys(sourcePerformance).forEach(source => {
      const perf = sourcePerformance[source];
      perf.conversionRate = perf.leads > 0 ? (perf.conversions / perf.leads) * 100 : 0;
    });
    
    return sourcePerformance;
  }
}