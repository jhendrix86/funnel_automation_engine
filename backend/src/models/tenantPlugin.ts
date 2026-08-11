import { Schema, Query } from 'mongoose';
import { getTenantId } from '../middleware/tenantContext';

/**
 * Mongoose equivalent of the SQLAlchemy `with_loader_criteria` +
 * `apply_tenant_context` pattern already used fleet-wide (see e.g.
 * content-engine's tenant_base.py). Adds a `tenantId` field, auto-assigns
 * it on create from the current request's tenant context if not already
 * set, and auto-scopes every read/update/delete query the same way -
 * callers never need to remember to filter by tenantId themselves.
 *
 * tenantId is intentionally not `required`/`unique`-constrained here,
 * matching the rest of the fleet's Stage 4 migration convention
 * (nullable until real tenant data exists everywhere).
 */
export function tenantScoped(schema: Schema): void {
  schema.add({ tenantId: { type: String, index: true } });

  schema.pre('save', function (next) {
    const tenantId = getTenantId();
    if (tenantId && this.get('tenantId') == null) {
      this.set('tenantId', tenantId);
    }
    next();
  });

  function scopeQuery(this: Query<unknown, unknown>, next: (err?: Error) => void) {
    const tenantId = getTenantId();
    if (tenantId) {
      const query = this.getQuery();
      if (query.tenantId === undefined) {
        this.where({ tenantId });
      }
    }
    next();
  }

  // Query-document read/write paths the controllers actually use
  // (findById/findByIdAndUpdate/findByIdAndDelete all resolve to
  // findOne/findOneAndUpdate/findOneAndDelete under the hood in mongoose).
  schema.pre('find', scopeQuery);
  schema.pre('findOne', scopeQuery);
  schema.pre('findOneAndUpdate', scopeQuery);
  schema.pre('findOneAndDelete', scopeQuery);
  schema.pre('findOneAndReplace', scopeQuery);
  schema.pre('countDocuments', scopeQuery);
  schema.pre('count', scopeQuery);
  // deleteOne/updateOne/deleteMany/updateMany are ambiguous in mongoose 7 -
  // they exist as BOTH query middleware (Model.deleteOne(filter)) and
  // document middleware (doc.deleteOne()). Only the query form needs
  // scoping (a document instance already refers to one specific,
  // already-loaded record); { document: false, query: true } picks that
  // overload explicitly rather than guessing which one mongoose infers.
  schema.pre('deleteOne', { document: false, query: true }, scopeQuery);
  schema.pre('updateOne', { document: false, query: true }, scopeQuery);
  schema.pre('deleteMany', scopeQuery);
  schema.pre('updateMany', scopeQuery);
}
