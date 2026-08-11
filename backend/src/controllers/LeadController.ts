import { Request, Response } from 'express';
import { Lead } from '../models/Lead';
import { Funnel } from '../models/Funnel';
import { AppError } from '../middleware/errorHandler';
import { cacheSet, cacheDeletePattern } from '../services/redisService';
import { emitToRoom } from '../services/socketService';
import { logger } from '../utils/logger';

export class LeadController {
  async createLead(req: Request, res: Response) {
    const { email, firstName, lastName, phone, company, source, funnelId, landingPage, variant, leadMagnet, metadata } = req.body;
    
    // Check if funnel exists
    const funnel = await Funnel.findById(funnelId);
    if (!funnel) {
      throw new AppError('Funnel not found', 404);
    }
    
    // Check if lead already exists
    let lead = await Lead.findOne({ email });
    
    if (lead) {
      // Update existing lead
      lead.firstName = firstName || lead.firstName;
      lead.lastName = lastName || lead.lastName;
      lead.phone = phone || lead.phone;
      lead.company = company || lead.company;
      lead.landingPage = landingPage || lead.landingPage;
      lead.variant = variant || lead.variant;
      lead.leadMagnet = leadMagnet || lead.leadMagnet;
      lead.metadata = { ...lead.metadata, ...metadata };
      
      await lead.save();
      logger.info(`Existing lead updated: ${email}`);
    } else {
      // Create new lead
      lead = new Lead({
        email,
        firstName,
        lastName,
        phone,
        company,
        source,
        funnelId,
        landingPage,
        variant,
        leadMagnet,
        metadata,
        score: 0,
        status: 'new'
      });
      
      await lead.save();
      
      // Update funnel analytics
      funnel.analytics.leads += 1;
      await funnel.save();
      
      logger.info(`New lead created: ${email}`);
    }
    
    // Cache the lead
    await cacheSet(`lead:${lead._id}`, lead);
    
    // Emit real-time update
    emitToRoom(`funnel-${funnelId}`, 'lead-created', {
      leadId: lead._id,
      email: lead.email,
      source: lead.source,
      timestamp: new Date()
    });
    
    res.status(201).json(lead);
  }

  async getLeads(req: Request, res: Response) {
    const { status, score, funnelId, page = 1, limit = 10 } = req.query;
    
    const query: any = {};
    if (status) query.status = status;
    if (funnelId) query.funnelId = funnelId;
    if (score) query.score = { $gte: Number(score) };
    
    const leads = await Lead.find(query)
      .sort({ createdAt: -1 })
      .skip((Number(page) - 1) * Number(limit))
      .limit(Number(limit));
    
    const total = await Lead.countDocuments(query);
    
    res.json({
      leads,
      pagination: {
        page: Number(page),
        limit: Number(limit),
        total,
        pages: Math.ceil(total / Number(limit))
      }
    });
  }

  async getLead(req: Request, res: Response) {
    const lead = await Lead.findById(req.params.id);
    
    if (!lead) {
      throw new AppError('Lead not found', 404);
    }
    
    res.json(lead);
  }

  async updateLead(req: Request, res: Response) {
    const lead = await Lead.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );
    
    if (!lead) {
      throw new AppError('Lead not found', 404);
    }
    
    await cacheSet(`lead:${lead._id}`, lead);
    
    logger.info(`Lead updated: ${lead._id}`);
    res.json(lead);
  }

  async deleteLead(req: Request, res: Response) {
    const lead = await Lead.findByIdAndDelete(req.params.id);
    
    if (!lead) {
      throw new AppError('Lead not found', 404);
    }
    
    await cacheDeletePattern(`lead:${lead._id}:*`);
    
    logger.info(`Lead deleted: ${lead._id}`);
    res.status(204).send();
  }

  async trackBehavior(req: Request, res: Response) {
    const { type, data, page, element } = req.body;
    
    const lead = await Lead.findById(req.params.id);
    if (!lead) {
      throw new AppError('Lead not found', 404);
    }
    
    // Add behavior
    lead.behaviors.push({
      type,
      timestamp: new Date(),
      data,
      page,
      element
    });
    
    // Update lead score
    await lead.updateScore();
    
    await lead.save();
    
    // Emit real-time update
    emitToRoom(`funnel-${lead.funnelId}`, 'lead-behavior', {
      leadId: lead._id,
      behaviorType: type,
      score: lead.score,
      timestamp: new Date()
    });
    
    logger.info(`Behavior tracked for lead ${lead._id}: ${type}`);
    res.json({ success: true, score: lead.score });
  }

  async updateScore(req: Request, res: Response) {
    const lead = await Lead.findById(req.params.id);
    if (!lead) {
      throw new AppError('Lead not found', 404);
    }
    
    await lead.updateScore();
    
    // Update status based on score
    if (lead.score >= 50) {
      lead.status = 'qualified';
    } else if (lead.score >= 20) {
      lead.status = 'nurturing';
    }
    
    await lead.save();
    
    await cacheSet(`lead:${lead._id}`, lead);
    
    logger.info(`Lead score updated: ${lead._id} -> ${lead.score}`);
    res.json({ score: lead.score, status: lead.status });
  }

  async getLeadsByFunnel(req: Request, res: Response) {
    const { funnelId } = req.params;
    const { status, page = 1, limit = 10 } = req.query;
    
    const query: any = { funnelId };
    if (status) query.status = status;
    
    const leads = await Lead.find(query)
      .sort({ createdAt: -1 })
      .skip((Number(page) - 1) * Number(limit))
      .limit(Number(limit));
    
    const total = await Lead.countDocuments(query);
    
    res.json({
      leads,
      pagination: {
        page: Number(page),
        limit: Number(limit),
        total,
        pages: Math.ceil(total / Number(limit))
      }
    });
  }

  async segmentLeads(req: Request, res: Response) {
    const { criteria } = req.body;
    
    const query: any = {};
    
    if (criteria.status) {
      query.status = criteria.status;
    }
    
    if (criteria.scoreRange) {
      query.score = {
        $gte: criteria.scoreRange.min,
        $lte: criteria.scoreRange.max
      };
    }
    
    if (criteria.source) {
      query.source = criteria.source;
    }
    
    if (criteria.behaviorType) {
      query['behaviors.type'] = criteria.behaviorType;
    }
    
    if (criteria.dateRange) {
      query.createdAt = {
        $gte: new Date(criteria.dateRange.start),
        $lte: new Date(criteria.dateRange.end)
      };
    }
    
    const leads = await Lead.find(query).sort({ score: -1 });
    
    logger.info(`Leads segmented: ${leads.length} leads match criteria`);
    res.json({
      segments: leads,
      count: leads.length
    });
  }
}