import { Server as SocketServer } from 'socket.io';
import type { Server as HTTPServer } from 'http';
import { logger } from '../utils/logger';

let io: SocketServer | undefined;

/**
 * Owns Socket.IO server creation/access, the same way redisService.ts owns
 * the Redis client. Controllers previously did `import { io } from
 * '../index'` directly - a real bug, not just an ugly import: it created a
 * circular dependency (index.ts -> app.ts -> routes -> controllers ->
 * index.ts) that only happened to work because everything used to live in
 * one file. Splitting app construction out of index.ts (for testability)
 * broke it for real: importing app.ts directly, as tests now do, throws
 * `ReferenceError: Cannot access 'trafficRoutes_1' before initialization`
 * because index.ts's own top-level `createApp()` call re-enters app.ts's
 * module evaluation before its own imports have finished resolving.
 */
export function initSocketServer(httpServer: HTTPServer): SocketServer {
  io = new SocketServer(httpServer, {
    cors: {
      origin: process.env.FRONTEND_URL || '*',
      methods: ['GET', 'POST'],
    },
  });
  return io;
}

/**
 * Real-time updates are a best-effort side channel, not the primary
 * operation - a lead/funnel write must still succeed even if nothing is
 * listening (e.g. under test, or if the socket server hasn't started yet).
 * Same "don't let a best-effort side effect crash an already-correct
 * result" pattern applied to Redis caching and, earlier this session, to
 * governance-engine's event emission.
 */
export function emitToRoom(room: string, event: string, payload: unknown): void {
  if (!io) {
    logger.warn(`Socket.IO not initialized - dropped "${event}" for room ${room}`);
    return;
  }
  io.to(room).emit(event, payload);
}
