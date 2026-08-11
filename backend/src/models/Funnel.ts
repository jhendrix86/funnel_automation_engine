import { Schema, model, Document } from 'mongoose';
import { tenantScoped } from './tenantPlugin';

export interface IDailyStat {
  date: Date;
  visitors: number;
  leads: number;
  conversions: number;
  revenue: number;
}

export interface IVariant {
  id: string;
  name: string;
  visitors: number;
  conversions: number;
  conversionRate: number;
}

export interface ILandingPage {
  name: string;
  url: string;
  variants: IVariant[];
}

export interface ITrafficSource {
  type: string;
  priority: number;
  budget?: number;
}

export interface ILeadMagnet {
  name: string;
  type: string;
  isActive: boolean;
  conversionRate: number;
}

export interface IEmailSequenceStats {
  sent: number;
  opened: number;
  clicked: number;
  converted: number;
}

export interface IEmailSequence {
  name: string;
  isActive: boolean;
  stats: IEmailSequenceStats;
}

export interface IFunnelAnalytics {
  visitors: number;
  leads: number;
  conversions: number;
  revenue: number;
  conversionRate: number;
  trafficBreakdown: Record<string, number>;
  dailyStats: IDailyStat[];
}

export interface IFunnel extends Document {
  tenantId?: string;
  name: string;
  description?: string;
  status: 'active' | 'paused' | 'archived';
  settings: Record<string, any>;
  trafficSources: ITrafficSource[];
  landingPages: ILandingPage[];
  leadMagnets: ILeadMagnet[];
  emailSequences: IEmailSequence[];
  analytics: IFunnelAnalytics;
  createdAt: Date;
  updatedAt: Date;
}

const dailyStatSchema = new Schema<IDailyStat>(
  {
    date: { type: Date, required: true },
    visitors: { type: Number, default: 0 },
    leads: { type: Number, default: 0 },
    conversions: { type: Number, default: 0 },
    revenue: { type: Number, default: 0 }
  },
  { _id: false }
);

const variantSchema = new Schema<IVariant>(
  {
    id: { type: String, required: true },
    name: { type: String, required: true },
    visitors: { type: Number, default: 0 },
    conversions: { type: Number, default: 0 },
    conversionRate: { type: Number, default: 0 }
  },
  { _id: false }
);

const landingPageSchema = new Schema<ILandingPage>({
  name: { type: String, required: true },
  url: { type: String, required: true },
  variants: { type: [variantSchema], default: [] }
});

const trafficSourceSchema = new Schema<ITrafficSource>({
  type: { type: String, required: true },
  priority: { type: Number, default: 0 },
  budget: { type: Number }
});

const leadMagnetSchema = new Schema<ILeadMagnet>({
  name: { type: String, required: true },
  type: { type: String, required: true },
  isActive: { type: Boolean, default: true },
  conversionRate: { type: Number, default: 0 }
});

const emailSequenceSchema = new Schema<IEmailSequence>({
  name: { type: String, required: true },
  isActive: { type: Boolean, default: true },
  stats: {
    sent: { type: Number, default: 0 },
    opened: { type: Number, default: 0 },
    clicked: { type: Number, default: 0 },
    converted: { type: Number, default: 0 }
  }
});

const funnelSchema = new Schema<IFunnel>(
  {
    name: { type: String, required: true, trim: true },
    description: { type: String },
    status: {
      type: String,
      enum: ['active', 'paused', 'archived'],
      default: 'active',
      index: true
    },
    settings: { type: Schema.Types.Mixed, default: {} },
    trafficSources: { type: [trafficSourceSchema], default: [] },
    landingPages: { type: [landingPageSchema], default: [] },
    leadMagnets: { type: [leadMagnetSchema], default: [] },
    emailSequences: { type: [emailSequenceSchema], default: [] },
    analytics: {
      visitors: { type: Number, default: 0 },
      leads: { type: Number, default: 0 },
      conversions: { type: Number, default: 0 },
      revenue: { type: Number, default: 0 },
      conversionRate: { type: Number, default: 0 },
      trafficBreakdown: { type: Schema.Types.Mixed, default: {} },
      dailyStats: { type: [dailyStatSchema], default: [] }
    }
  },
  { timestamps: true }
);

tenantScoped(funnelSchema);

export const Funnel = model<IFunnel>('Funnel', funnelSchema);
