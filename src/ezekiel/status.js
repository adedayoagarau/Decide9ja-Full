const Queue = require('bull');
const winston = require('winston');

// Configuration - must match orchestrator.js
const CONFIG = {
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
  queues: {
    parse: { name: 'parse', concurrency: 3 },
    chunk: { name: 'chunk', concurrency: 2 },
    embed: { name: 'embed', concurrency: 4 },
    entity: { name: 'entity', concurrency: 2 },
    ingest: { name: 'ingest', concurrency: 2 }
  }
};

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

async function getQueueMetrics(queueName) {
  const queue = new Queue(queueName, CONFIG.redisUrl);
  try {
    const counts = await queue.getJobCounts();
    const waiting = await queue.getWaitingCount();
    const active = await queue.getActiveCount();
    const completed = await queue.getCompletedCount();
    const failed = await queue.getFailedCount();
    const delayed = await queue.getDelayedCount();
    const paused = await queue.getPausedCount();

    const metrics = {
      name: queueName,
      waiting,
      active,
      completed,
      failed,
      delayed,
      paused,
      total: waiting + active + completed + failed + delayed + paused,
      ...counts
    };
    await queue.close();
    return metrics;
  } catch (error) {
    logger.error(`Error fetching metrics for queue ${queueName}:`, error);
    await queue.close();
    return { name: queueName, error: error.message };
  }
}

async function main() {
  const allMetrics = [];
  logger.info('--- Ezekiel Pipeline Status ---');

  for (const key in CONFIG.queues) {
    const queueName = CONFIG.queues[key].name;
    const metrics = await getQueueMetrics(queueName);
    allMetrics.push(metrics);
  }
  
  logger.info(JSON.stringify(allMetrics, null, 2));

  // Basic processing rate estimation (very crude, based on completed jobs)
  // This would ideally need more sophisticated tracking, e.g., using Redis's built-in metrics
  const totalCompleted = allMetrics.reduce((sum, q) => sum + (q.completed || 0), 0);
  logger.info(`Total completed jobs across all queues: ${totalCompleted}`);

  const totalFailed = allMetrics.reduce((sum, q) => sum + (q.failed || 0), 0);
  logger.info(`Total failed jobs across all queues: ${totalFailed}`);
  
  // Exit with error if any queue has failed jobs or isn't reachable
  const hasErrors = allMetrics.some(m => m.error || m.failed > 0);
  if (hasErrors) {
      process.exit(1);
  }
}

main().catch(error => {
  logger.error('Ezekiel status script failed:', error);
  process.exit(1);
});
