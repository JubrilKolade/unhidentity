const webhookService = require('../services/webhook.service');
const logger = require('../utils/logger');

async function retryFailedWebhooks() {
  try {
    logger.info('Starting webhook retry job...');
    const retried = await webhookService.retryFailedWebhooks();
    logger.info(`Webhook retry job completed. Retried: ${retried} webhooks`);
  } catch (error) {
    logger.error(`Webhook retry job failed: ${error.message}`);
  }
}

// Run every 5 minutes
setInterval(retryFailedWebhooks, 5 * 60 * 1000);

// Run immediately on start
retryFailedWebhooks();

module.exports = retryFailedWebhooks;