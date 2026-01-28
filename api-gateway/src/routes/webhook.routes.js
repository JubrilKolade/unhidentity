const express = require('express');
const router = express.Router();
const webhookController = require('../controllers/webhook.controller');
const { authenticateApiKey } = require('../middleware/auth.middleware');

router.use(authenticateApiKey);

// Get webhook delivery history
router.get('/history', webhookController.getWebhookHistory);

// Retry a specific webhook
router.post('/retry/:id', webhookController.retryWebhook);

// Test webhook configuration
router.post('/test', webhookController.testWebhook);

module.exports = router;