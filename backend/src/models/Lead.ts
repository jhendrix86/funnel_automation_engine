import { Schema, model, Document, Types } from 'mongoose';
import { tenantScoped } from './tenantPlugin';

export interface IBehavior {
  type: string;
  timestamp: Date;
  data?: any;
  page?: string;
  element?: string;
}

export interface ILead extends Document {
  tenantId?: string;
  email: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
  company?: string;
  source: string;
  funnelId: Types.ObjectId;
  landingPage?: string;
  variant?: string;
  leadMagnet?: string;
  metadata: Record<string, any>;
  score: number;
  status: 'new' | 'qualified' | 'nurturing' | 'converted' | 'lost';
  behaviors: IBehavior[];
  createdAt: Date;
  updatedAt: Date;
  updateScore(): Promise<number>;
}

const behaviorSchema = new Schema<IBehavior>(
  {
    type: { type: String, required: true },
    timestamp: { type: Date, default: Date.now },
    data: { type: Schema.Types.Mixed },
    page: { type: String },
    element: { type: String }
  },
  { _id: false }
);

const leadSchema = new Schema<ILead>(
  {
    // Not field-level `unique` - uniqueness is scoped per-tenant (see the
    // compound index below), otherwise two different tenants could never
    // both have a lead with the same email address.
    email: { type: String, required: true, lowercase: true, trim: true },
    firstName: { type: String },
    lastName: { type: String },
    phone: { type: String },
    company: { type: String },
    source: { type: String, default: 'direct' },
    funnelId: { type: Schema.Types.ObjectId, ref: 'Funnel', required: true, index: true },
    landingPage: { type: String },
    variant: { type: String },
    leadMagnet: { type: String },
    metadata: { type: Schema.Types.Mixed, default: {} },
    score: { type: Number, default: 0 },
    status: {
      type: String,
      enum: ['new', 'qualified', 'nurturing', 'converted', 'lost'],
      default: 'new',
      index: true
    },
    behaviors: { type: [behaviorSchema], default: [] }
  },
  { timestamps: true }
);

leadSchema.index({ funnelId: 1, status: 1 });
leadSchema.index({ score: -1 });
leadSchema.index({ tenantId: 1, email: 1 }, { unique: true });

// Rough engagement weighting per behavior type; caps total at 100.
const BEHAVIOR_SCORE_WEIGHTS: Record<string, number> = {
  page_view: 1,
  click: 2,
  email_open: 3,
  email_click: 5,
  form_start: 5,
  video_watch: 8,
  download: 10,
  form_submit: 10
};

leadSchema.methods.updateScore = async function (this: ILead): Promise<number> {
  const rawScore = this.behaviors.reduce(
    (sum, behavior) => sum + (BEHAVIOR_SCORE_WEIGHTS[behavior.type] ?? 1),
    0
  );
  this.score = Math.min(rawScore, 100);
  return this.score;
};

tenantScoped(leadSchema);

export const Lead = model<ILead>('Lead', leadSchema);
