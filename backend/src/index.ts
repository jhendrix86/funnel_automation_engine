import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import dotenv from 'dotenv';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/errorHandler';
import { trafficRoutes } from './routes/trafficRoutes';
import { leadRoutes } from './routes/leadRoutes';
import { funnelRoutes } from './routes/funnelRoutes';
import { analyticsRoutes } from './routes/analyticsRoutes';
import { connectRedis } from './services/redisService';
import { connectDatabase } from './services/databaseService';

dotenv.config();

const app = express();
const httpServer = createServer(app);
const io = new SocketServer(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL || '*',
    methods: ['GET', 'POST']
  }
});

// Rate limiting for DDoS protection
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 10000, // Limit each IP to 10000 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});

// Middleware
app.use(helmet());
app.use(cors());
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(limiter);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// API Routes
app.use('/api/traffic', trafficRoutes);
app.use('/api/leads', leadRoutes);
app.use('/api/funnels', funnelRoutes);
app.use('/api/analytics', analyticsRoutes);

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

// Error handling
app.use(errorHandler);

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

export { io };