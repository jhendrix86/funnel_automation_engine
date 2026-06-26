import { Request, Response } from 'express';
import { Funnel, IFunnel } from '../models/Funnel';
import { AppError } from '../middleware/errorHandler';
import { cacheSet, cacheDeletePattern } from '../services/redisService';
import { logger } from '../utils/logger';

export class FunnelController {
  async createFunnel(req: Request, res: Response) {
    const funnel = new Funnel(req.body);
    await funnel.save();
    
    // Cache the new funnel
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Funnel created: ${funnel._id}`);
    res.status(201).json(funnel);
  }

  async getFunnels(req: Request, res: Response) {
    const { status, page = 1, limit = 10 } = req.query;
    
    const query: any = {};
    if (status) query.status = status;
    
    const funnels = await Funnel.find(query)
      .sort({ createdAt: -1 })
      .skip((Number(page) - 1) * Number(limit))
      .limit(Number(limit));
    
    const total = await Funnel.countDocuments(query);
    
    res.json({
      funnels,
      pagination: {
        page: Number(page),
        limit: Number(limit),
        total,
        pages: Math.ceil(total / Number(limit))
      }
    });
  }

  async getFunnel(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    res.json(funnel);
  }

  async updateFunnel(req: Request, res: Response) {
    const funnel = await Funnel.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Update cache
    await cacheSet(`funnel:${funnel._id}`, funnel);
    await cacheDeletePattern(`funnel:${funnel._id}:*`);
    
    logger.info(`Funnel updated: ${funnel._id}`);
    res.json(funnel);
  }

  async deleteFunnel(req: Request, res: Response) {
    const funnel = await Funnel.findByIdAndDelete(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Clear cache
    await cacheDeletePattern(`funnel:${funnel._id}:*`);
    
    logger.info(`Funnel deleted: ${funnel._id}`);
    res.status(204).send();
  }

  async updateFunnelStatus(req: Request, res: Response) {
    const { status } = req.body;
    
    if (!['active', 'paused', 'archived'].includes(status)) {
      throw new AppError('Invalid status value', 400);
    }
    
    const funnel = await Funnel.findByIdAndUpdate(
      req.params.id,
      { status },
      { new: true }
    );
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Funnel status updated: ${funnel._id} -> ${status}`);
    res.json(funnel);
  }

  async getFunnelAnalytics(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    const { startDate, endDate } = req.query;
    
    let analytics = funnel.analytics;
    
    if (startDate || endDate) {
      const start = startDate ? new Date(startDate as string) : new Date(0);
      const end = endDate ? new Date(endDate as string) : new Date();
      
      analytics.dailyStats = funnel.analytics.dailyStats.filter(
        (stat) => stat.date >= start && stat.date <= end
      );
      
      // Recalculate totals for the date range
      analytics.visitors = analytics.dailyStats.reduce((sum, stat) => sum + stat.visitors, 0);
      analytics.leads = analytics.dailyStats.reduce((sum, stat) => sum + stat.leads, 0);
      analytics.conversions = analytics.dailyStats.reduce((sum, stat) => sum + stat.conversions, 0);
      analytics.revenue = analytics.dailyStats.reduce((sum, stat) => sum + stat.revenue, 0);
      analytics.conversionRate = analytics.visitors > 0 ? (analytics.conversions / analytics.visitors) * 100 : 0;
    }
    
    res.json(analytics);
  }

  async updateFunnelSettings(req: Request, res: Response) {
    const funnel = await Funnel.findByIdAndUpdate(
      req.params.id,
      { $set: { settings: req.body } },
      { new: true }
    );
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Funnel settings updated: ${funnel._id}`);
    res.json(funnel.settings);
  }

  async addTrafficSource(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    funnel.trafficSources.push(req.body);
    await funnel.save();
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Traffic source added to funnel: ${funnel._id}`);
    res.json(funnel.trafficSources[funnel.trafficSources.length - 1]);
  }

  async addLandingPage(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    funnel.landingPages.push(req.body);
    await funnel.save();
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Landing page added to funnel: ${funnel._id}`);
    res.json(funnel.landingPages[funnel.landingPages.length - 1]);
  }

  async addLeadMagnet(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    funnel.leadMagnets.push(req.body);
    await funnel.save();
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Lead magnet added to funnel: ${funnel._id}`);
    res.json(funnel.leadMagnets[funnel.leadMagnets.length - 1]);
  }

  async addEmailSequence(req: Request, res: Response) {
    const funnel = await Funnel.findById(req.params.id);
    
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    funnel.emailSequences.push(req.body);
    await funnel.save();
    
    await cacheSet(`funnel:${funnel._id}`, funnel);
    
    logger.info(`Email sequence added to funnel: ${funnel._id}`);
    res.json(funnel.emailSequences[funnel.emailSequences.length - 1]);
  }
}