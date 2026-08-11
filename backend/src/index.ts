import { createServer } from 'http';
import dotenv from 'dotenv';
import { logger } from './utils/logger';
import { createApp } from './app';
import { connectRedis } from './services/redisService';
import { connectDatabase } from './services/databaseService';
import { initSocketServer } from './services/socketService';

dotenv.config();

const app = createApp();
const httpServer = createServer(app);
const io = initSocketServer(httpServer);

// WebSocket for real-time analytics
io.on('connection', (socket) => {
  logger.info(`Client connected: ${socket.id}`);

  socket.on('subscribe-funnel', (funnelId: string) => {
    socket.join(`funnel-${funnelId}`);
    logger.info(`Client ${socket.id} subscribed to funnel ${funnelId}`);
  });

  socket.on('disconnect', () => {
    logger.info(`Client disconnected: ${socket.id}`);
  });
});

// Start server
const PORT = process.env.PORT || 3000;

async function startServer() {
  try {
    await connectRedis();
    await connectDatabase();

    httpServer.listen(PORT, () => {
      logger.info(`Traffic Funnel Engine running on port ${PORT}`);
      logger.info(`Environment: ${process.env.NODE_ENV || 'development'}`);
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
