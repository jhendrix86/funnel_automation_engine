import { Request, Response } from 'express';
import { Funnel } from '../models/Funnel';
import { Lead } from '../models/Lead';
import { AppError } from '../middleware/errorHandler';
import { cacheGet, cacheSet } from '../services/redisService';
import { logger } from '../utils/logger';

export class AnalyticsController {
  async getDashboardAnalytics(req: Request, res: Response) {
    const { timeRange = '7d' } = req.query;
    
    // Calculate date range
    const endDate = new Date();
    const startDate = new Date();
    
    switch (timeRange) {
      case '24h':
        startDate.setHours(startDate.getHours() - 24);
        break;
      case '7d':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(startDate.getDate() - 30);
        break;
      case '90d':
        startDate.setDate(startDate.getDate() - 90);
        break;
      default:
        startDate.setDate(startDate.getDate() - 7);
    }
    
    // Get all active funnels
    const funnels = await Funnel.find({ status: 'active' });
    
    // Aggregate metrics
    let totalVisitors = 0;
    let totalLeads = 0;
    let totalConversions = 0;
    let totalRevenue = 0;
    const trafficBreakdown: Record<string, number> = {};
    const funnelPerformance: any[] = [];
    
    for (const funnel of funnels) {
      // Filter daily stats by date range
      const relevantStats = funnel.analytics.dailyStats.filter(
        stat => stat.date >= startDate && stat.date <= endDate
      );
      
      const visitors = relevantStats.reduce((sum, stat) => sum + stat.visitors, 0);
      const leads = relevantStats.reduce((sum, stat) => sum + stat.leads, 0);
      const conversions = relevantStats.reduce((sum, stat) => sum + stat.conversions, 0);
      const revenue = relevantStats.reduce((sum, stat) => sum + stat.revenue, 0);
      
      totalVisitors += visitors;
      totalLeads += leads;
      totalConversions += conversions;
      totalRevenue += revenue;
      
      // Aggregate traffic breakdown
      Object.entries(funnel.analytics.trafficBreakdown).forEach(([source, count]) => {
        trafficBreakdown[source] = (trafficBreakdown[source] || 0) + (count as number);
      });
      
      // Funnel performance
      funnelPerformance.push({
        funnelId: funnel._id,
        name: funnel.name,
        visitors,
        leads,
        conversions,
        revenue,
        conversionRate: visitors > 0 ? (conversions / visitors) * 100 : 0,
        leadRate: visitors > 0 ? (leads / visitors) * 100 : 0
      });
    }
    
    const overallConversionRate = totalVisitors > 0 ? (totalConversions / totalVisitors) * 100 : 0;
    const overallLeadRate = totalVisitors > 0 ? (totalLeads / totalVisitors) * 100 : 0;
    const averageOrderValue = totalConversions > 0 ? totalRevenue / totalConversions : 0;
    
    const dashboardData = {
      timeRange,
      period: { startDate, endDate },
      overview: {
        totalVisitors,
        totalLeads,
        totalConversions,
        totalRevenue,
        overallConversionRate,
        overallLeadRate,
        averageOrderValue
      },
      trafficBreakdown,
      funnelPerformance: funnelPerformance.sort((a, b) => b.conversions - a.conversions),
      activeFunnels: funnels.length
    };
    
    // Cache for 5 minutes
    await cacheSet(`analytics:dashboard:${timeRange}`, dashboardData, 300);
    
    res.json(dashboardData);
  }

  async getFunnelPerformance(req: Request, res: Response) {
    const { funnelId } = req.params;
    const { timeRange = '7d' } = req.query;
    
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Calculate date range
    const endDate = new Date();
    const startDate = new Date();
    
    switch (timeRange) {
      case '24h':
        startDate.setHours(startDate.getHours() - 24);
        break;
      case '7d':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(startDate.getDate() - 30);
        break;
      default:
        startDate.setDate(startDate.getDate() - 7);
    }
    
    // Filter daily stats
    const relevantStats = funnel.analytics.dailyStats.filter(
      stat => stat.date >= startDate && stat.date <= endDate
    );
    
    // Calculate metrics
    const visitors = relevantStats.reduce((sum, stat) => sum + stat.visitors, 0);
    const leads = relevantStats.reduce((sum, stat) => sum + stat.leads, 0);
    const conversions = relevantStats.reduce((sum, stat) => sum + stat.conversions, 0);
    const revenue = relevantStats.reduce((sum, stat) => sum + stat.revenue, 0);
    
    // Landing page performance
    const landingPagePerformance = funnel.landingPages.map(page => ({
      name: page.name,
      url: page.url,
      visitors: page.variants.reduce((sum, variant) => sum + variant.visitors, 0),
      conversions: page.variants.reduce((sum, variant) => sum + variant.conversions, 0),
      conversionRate: page.variants.reduce((sum, variant) => sum + variant.visitors, 0) > 0
        ? (page.variants.reduce((sum, variant) => sum + variant.conversions, 0) / 
           page.variants.reduce((sum, variant) => sum + variant.visitors, 0)) * 100
        : 0,
      variants: page.variants.map(variant => ({
        id: variant.id,
        name: variant.name,
        visitors: variant.visitors,
        conversions: variant.conversions,
        conversionRate: variant.conversionRate
      }))
    }));
    
    // Lead magnet performance
    const leadMagnetPerformance = funnel.leadMagnets
      .filter(magnet => magnet.isActive)
      .map(magnet => ({
        name: magnet.name,
        type: magnet.type,
        conversionRate: magnet.conversionRate
      }));
    
    // Email sequence performance
    const emailSequencePerformance = funnel.emailSequences
      .filter(sequence => sequence.isActive)
      .map(sequence => ({
        name: sequence.name,
        emailsSent: sequence.stats.sent,
        openRate: sequence.stats.sent > 0 ? (sequence.stats.opened / sequence.stats.sent) * 100 : 0,
        clickRate: sequence.stats.opened > 0 ? (sequence.stats.clicked / sequence.stats.opened) * 100 : 0,
        conversionRate: sequence.stats.sent > 0 ? (sequence.stats.converted / sequence.stats.sent) * 100 : 0
      }));
    
    const performanceData = {
      funnelId: funnel._id,
      funnelName: funnel.name,
      timeRange,
      period: { startDate, endDate },
      overview: {
        visitors,
        leads,
        conversions,
        revenue,
        conversionRate: visitors > 0 ? (conversions / visitors) * 100 : 0,
        leadRate: visitors > 0 ? (leads / visitors) * 100 : 0,
        averageOrderValue: conversions > 0 ? revenue / conversions : 0
      },
      trafficBreakdown: funnel.analytics.trafficBreakdown,
      landingPages: landingPagePerformance,
      leadMagnets: leadMagnetPerformance,
      emailSequences: emailSequencePerformance,
      dailyStats: relevantStats
    };
    
    res.json(performanceData);
  }

  async getConversionTrends(req: Request, res: Response) {
    const { funnelId, timeRange = '30d' } = req.query;
    
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    
    let funnels = [];
    if (funnelId) {
      const funnel = await Funnel.findById(funnelId);
      if (!funnel) {
        throw new AppError('Funnel not found', 404);
      }
      funnels = [funnel];
    } else {
      funnels = await Funnel.find({ status: 'active' });
    }
    
    // Aggregate daily conversion data
    const dailyTrends: Record<string, any> = {};
    
    funnels.forEach(funnel => {
      funnel.analytics.dailyStats.forEach(stat => {
        if (stat.date >= startDate && stat.date <= endDate) {
          const dateKey = stat.date.toISOString().split('T')[0];
          if (!dailyTrends[dateKey]) {
            dailyTrends[dateKey] = {
              date: dateKey,
              visitors: 0,
              leads: 0,
              conversions: 0,
              revenue: 0
            };
          }
          dailyTrends[dateKey].visitors += stat.visitors;
          dailyTrends[dateKey].leads += stat.leads;
          dailyTrends[dateKey].conversions += stat.conversions;
          dailyTrends[dateKey].revenue += stat.revenue;
        }
      });
    });
    
    // Convert to array and sort by date
    const trends = Object.values(dailyTrends).sort((a, b) => 
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    
    // Calculate moving averages
    const conversionTrend = trends.map((trend, index) => {
      const slice = trends.slice(Math.max(0, index - 6), index + 1);
      const avgConversions = slice.reduce((sum, t) => sum + t.conversions, 0) / slice.length;
      const avgRevenue = slice.reduce((sum, t) => sum + t.revenue, 0) / slice.length;
      
      return {
        ...trend,
        movingAvgConversions: Math.round(avgConversions * 100) / 100,
        movingAvgRevenue: Math.round(avgRevenue * 100) / 100,
        conversionRate: trend.visitors > 0 ? (trend.conversions / trend.visitors) * 100 : 0
      };
    });
    
    res.json({
      timeRange,
      period: { startDate, endDate },
      trends: conversionTrend
    });
  }

  async getLeadQualityMetrics(req: Request, res: Response) {
    const { funnelId } = req.query;
    
    const query: any = {};
    if (funnelId) query.funnelId = funnelId;
    
    const leads = await Lead.find(query);
    
    // Calculate lead quality metrics
    const totalLeads = leads.length;
    const qualifiedLeads = leads.filter(lead => lead.status === 'qualified').length;
    const nurturingLeads = leads.filter(lead => lead.status === 'nurturing').length;
    const convertedLeads = leads.filter(lead => lead.status === 'converted').length;
    const lostLeads = leads.filter(lead => lead.status === 'lost').length;
    
    // Score distribution
    const scoreDistribution = {
      low: leads.filter(lead => lead.score < 20).length,
      medium: leads.filter(lead => lead.score >= 20 && lead.score < 50).length,
      high: leads.filter(lead => lead.score >= 50).length
    };
    
    // Average score by status
    const avgScoreByStatus: Record<string, number> = {};
    ['new', 'qualified', 'nurturing', 'converted', 'lost'].forEach(status => {
      const statusLeads = leads.filter(lead => lead.status === status);
      if (statusLeads.length > 0) {
        avgScoreByStatus[status] = statusLeads.reduce((sum, lead) => sum + lead.score, 0) / statusLeads.length;
      }
    });
    
    // Behavior analysis
    const behaviorAnalysis: Record<string, number> = {};
    leads.forEach(lead => {
      lead.behaviors.forEach(behavior => {
        behaviorAnalysis[behavior.type] = (behaviorAnalysis[behavior.type] || 0) + 1;
      });
    });
    
    // Source quality
    const sourceQuality: Record<string, any> = {};
    leads.forEach(lead => {
      if (!sourceQuality[lead.source]) {
        sourceQuality[lead.source] = {
          total: 0,
          qualified: 0,
          converted: 0,
          avgScore: 0
        };
      }
      sourceQuality[lead.source].total += 1;
      if (lead.status === 'qualified') sourceQuality[lead.source].qualified += 1;
      if (lead.status === 'converted') sourceQuality[lead.source].converted += 1;
      sourceQuality[lead.source].avgScore += lead.score;
    });
    
    // Calculate averages and conversion rates by source
    Object.keys(sourceQuality).forEach(source => {
      const data = sourceQuality[source];
      data.avgScore = data.avgScore / data.total;
      data.qualificationRate = (data.qualified / data.total) * 100;
      data.conversionRate = (data.converted / data.total) * 100;
    });
    
    const qualityMetrics = {
      overview: {
        totalLeads,
        qualifiedLeads,
        nurturingLeads,
        convertedLeads,
        lostLeads,
        qualificationRate: totalLeads > 0 ? (qualifiedLeads / totalLeads) * 100 : 0,
        conversionRate: totalLeads > 0 ? (convertedLeads / totalLeads) * 100 : 0
      },
      scoreDistribution,
      avgScoreByStatus,
      behaviorAnalysis,
      sourceQuality
    };
    
    res.json(qualityMetrics);
  }

  async getTrafficSourceROI(req: Request, res: Response) {
    const { funnelId } = req.query;
    
    const query: any = {};
    if (funnelId) query.funnelId = funnelId;
    
    const leads = await Lead.find(query);
    const funnels = funnelId 
      ? await Funnel.findById(funnelId)
      : await Funnel.find({ status: 'active' });
    
    const funnelArray = Array.isArray(funnels) ? funnels : [funnels];
    
    // Calculate ROI by traffic source
    const sourceROI: Record<string, any> = {};
    
    leads.forEach(lead => {
      const source = lead.source;
      if (!sourceROI[source]) {
        sourceROI[source] = {
          leads: 0,
          qualified: 0,
          converted: 0,
          totalScore: 0,
          behaviors: 0
        };
      }
      
      sourceROI[source].leads += 1;
      if (lead.status === 'qualified') sourceROI[source].qualified += 1;
      if (lead.status === 'converted') sourceROI[source].converted += 1;
      sourceROI[source].totalScore += lead.score;
      sourceROI[source].behaviors += lead.behaviors.length;
    });
    
    // Add traffic cost and revenue data (would come from your cost tracking system)
    Object.keys(sourceROI).forEach(source => {
      const data = sourceROI[source];
      data.avgScore = data.totalScore / data.leads;
      data.avgBehaviors = data.behaviors / data.leads;
      data.qualificationRate = (data.qualified / data.leads) * 100;
      data.conversionRate = (data.converted / data.leads) * 100;
      
      // Get traffic volume from funnels
      let totalTraffic = 0;
      funnelArray.forEach(funnel => {
        totalTraffic += (funnel.analytics.trafficBreakdown[source] || 0);
      });
      
      data.trafficVolume = totalTraffic;
      data.leadRate = totalTraffic > 0 ? (data.leads / totalTraffic) * 100 : 0;
      
      // Calculate ROI score (weighted combination of metrics)
      data.roiScore = (
        (data.conversionRate * 0.4) +
        (data.qualificationRate * 0.3) +
        (data.leadRate * 0.2) +
        (data.avgScore / 100 * 0.1)
      );
    });
    
    // Sort by ROI score
    const sortedROI = Object.entries(sourceROI)
      .map(([source, data]) => ({ source, ...data }))
      .sort((a, b) => b.roiScore - a.roiScore);
    
    res.json({
      sourceROI: sortedROI,
      recommendations: this.generateROIRecommendations(sortedROI)
    });
  }

  async getRealTimeAnalytics(req: Request, res: Response) {
    const { funnelId } = req.query;
    
    // Get recent activity (last 5 minutes)
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    
    const query: any = {
      'behaviors.timestamp': { $gte: fiveMinutesAgo }
    };
    
    if (funnelId) query.funnelId = funnelId;
    
    const recentLeads = await Lead.find(query);
    
    // Calculate real-time metrics
    const activeVisitors = recentLeads.length;
    const recentBehaviors = recentLeads.reduce((sum, lead) => 
      sum + lead.behaviors.filter(b => b.timestamp >= fiveMinutesAgo).length, 0
    );
    
    // Get current funnel states
    const funnels = funnelId 
      ? await Funnel.findById(funnelId)
      : await Funnel.find({ status: 'active' });
    
    const funnelArray = Array.isArray(funnels) ? funnels : [funnels];
    
    const funnelStates = funnelArray.map(funnel => ({
      funnelId: funnel._id,
      name: funnel.name,
      status: funnel.status,
      currentVisitors: funnel.analytics.visitors,
      todayLeads: funnel.analytics.dailyStats
        .filter(stat => stat.date.toDateString() === new Date().toDateString())
        .reduce((sum, stat) => sum + stat.leads, 0),
      todayConversions: funnel.analytics.dailyStats
        .filter(stat => stat.date.toDateString() === new Date().toDateString())
        .reduce((sum, stat) => sum + stat.conversions, 0)
    }));
    
    res.json({
      timestamp: new Date(),
      activeVisitors,
      recentBehaviors,
      funnels: funnelStates,
      topPages: this.getTopPages(recentLeads),
      activityFeed: this.getActivityFeed(recentLeads, 10)
    });
  }

  async generatePerformanceReport(req: Request, res: Response) {
    const { funnelId, timeRange = '30d', format = 'json' } = req.body;
    
    // Get comprehensive analytics
    const funnel = funnelId ? await Funnel.findById(funnelId) : null;
    const dashboardData = await this.getDashboardAnalytics({ query: { timeRange } }, res);
    
    const report = {
      generatedAt: new Date(),
      timeRange,
      funnel: funnel ? {
        id: funnel._id,
        name: funnel.name,
        description: funnel.description
      } : null,
      summary: dashboardData,
      recommendations: this.generatePerformanceRecommendations(dashboardData)
    };
    
    if (format === 'json') {
      res.json(report);
    } else {
      // Would implement PDF/CSV generation here
      res.json({ message: 'Only JSON format currently supported' });
    }
  }

  private generateROIRecommendations(sortedROI: any[]) {
    const recommendations = [];
    
    if (sortedROI.length > 0) {
      const topSource = sortedROI[0];
      recommendations.push({
        type: 'scale',
        source: topSource.source,
        message: `Scale ${topSource.source} traffic - highest ROI score of ${topSource.roiScore.toFixed(2)}`
      });
    }
    
    const lowPerformers = sortedROI.filter(s => s.roiScore < 20);
    lowPerformers.forEach(source => {
      recommendations.push({
        type: 'optimize',
        source: source.source,
        message: `Optimize ${source.source} campaigns - low ROI score of ${source.roiScore.toFixed(2)}`
      });
    });
    
    return recommendations;
  }

  private generatePerformanceRecommendations(data: any) {
    const recommendations = [];
    
    if (data.overview.overallConversionRate < 2) {
      recommendations.push({
        type: 'conversion',
        priority: 'high',
        message: 'Conversion rate below 2% - review landing page copy and design'
      });
    }
    
    if (data.overall.overallLeadRate < 5) {
      recommendations.push({
        type: 'lead_capture',
        priority: 'medium',
        message: 'Lead capture rate below 5% - test new lead magnets'
      });
    }
    
    const lowPerformingFunnels = data.funnelPerformance.filter(f => f.conversionRate < 1);
    lowPerformingFunnels.forEach(funnel => {
      recommendations.push({
        type: 'funnel_optimization',
        priority: 'medium',
        message: `Funnel "${funnel.name}" underperforming - consider A/B testing`
      });
    });
    
    return recommendations;
  }

  private getTopPages(leads: any[], limit = 5) {
    const pageViews: Record<string, number> = {};
    
    leads.forEach(lead => {
      lead.behaviors.forEach(behavior => {
        if (behavior.type === 'page_view' && behavior.page) {
          pageViews[behavior.page] = (pageViews[behavior.page] || 0) + 1;
        }
      });
    });
    
    return Object.entries(pageViews)
      .map(([page, views]) => ({ page, views }))
      .sort((a, b) => b.views - a.views)
      .slice(0, limit);
  }

  private getActivityFeed(leads: any[], limit = 10) {
    const activities: any[] = [];
    
    leads.forEach(lead => {
      lead.behaviors.forEach(behavior => {
        activities.push({
          leadId: lead._id,
          email: lead.email,
          type: behavior.type,
          timestamp: behavior.timestamp,
          page: behavior.page,
          element: behavior.element
        });
      });
    });
    
    return activities
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, limit);
  }
}