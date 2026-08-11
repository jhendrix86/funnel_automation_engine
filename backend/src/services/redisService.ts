import { createClient, RedisClientType } from 'redis';
import { logger } from '../utils/logger';

let redisClient: RedisClientType | null = null;

export async function connectRedis(): Promise<void> {
  try {
    redisClient = createClient({
      url: process.env.REDIS_URL || 'redis://localhost:6379',
      socket: {
        reconnectStrategy: (retries) => {
          if (retries > 10) {
            logger.error('Redis reconnection attempts exhausted');
            return new Error('Redis reconnection failed');
          }
          return Math.min(retries * 100, 3000);
        }
      }
    });

    redisClient.on('error', (error) => {
      logger.error('Redis Client Error:', error);
    });

    redisClient.on('connect', () => {
      logger.info('Redis Client Connected');
    });

    await redisClient.connect();
    
    // Test connection
    await redisClient.ping();
    logger.info('Redis connection verified');
    
  } catch (error) {
    logger.error('Failed to connect to Redis:', error);
    throw error;
  }
}

export function getRedisClient(): RedisClientType {
  if (!redisClient) {
    throw new Error('Redis client not initialized');
  }
  return redisClient;
}

export async function disconnectRedis(): Promise<void> {
  try {
    if (redisClient) {
      await redisClient.quit();
      logger.info('Redis client disconnected');
    }
  } catch (error) {
    logger.error('Error disconnecting Redis:', error);
    throw error;
  }
}

// Cache utility functions - caching is a best-effort side effect, not the
// primary operation. Every controller call site does real Mongo work
// (funnel.save(), lead.save(), etc.) *before* touching the cache; letting
// a Redis hiccup (or Redis simply not being connected, e.g. under test)
// throw out of these functions would take down an otherwise-successful
// create/update/delete. Same "don't let a best-effort side effect destroy
// an already-correct result" fix applied to governance-engine and
// baselayer's event emission earlier this session - log and continue.
export async function cacheSet(key: string, value: any, ttl: number = 3600): Promise<void> {
  try {
    const client = getRedisClient();
    await client.setEx(key, ttl, JSON.stringify(value));
  } catch (error) {
    logger.warn(`cacheSet failed for key ${key}:`, error);
  }
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const client = getRedisClient();
    const data = await client.get(key);
    if (data) {
      return JSON.parse(data) as T;
    }
    return null;
  } catch (error) {
    logger.warn(`cacheGet failed for key ${key}:`, error);
    return null;
  }
}

export async function cacheDelete(key: string): Promise<void> {
  try {
    const client = getRedisClient();
    await client.del(key);
  } catch (error) {
    logger.warn(`cacheDelete failed for key ${key}:`, error);
  }
}

export async function cacheDeletePattern(pattern: string): Promise<void> {
  try {
    const client = getRedisClient();
    const keys = await client.keys(pattern);
    if (keys.length > 0) {
      await client.del(keys);
    }
  } catch (error) {
    logger.warn(`cacheDeletePattern failed for pattern ${pattern}:`, error);
  }
}