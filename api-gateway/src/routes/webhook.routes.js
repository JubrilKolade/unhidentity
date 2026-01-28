import express from 'express';
const router = express.Router();
import webhookController from '../controllers/webhook.controller.js';
import { authenticateApiKey } from '../middleware/auth.middleware.js';

router.use(authenticateApiKey);

// Get webhook delivery history
router.get('/history', webhookController.getWebhookHistory);

// Retry a specific webhook
router.post('/retry/:id', webhookController.retryWebhook);

// Test webhook configuration
router.post('/test', webhookController.testWebhook);

export default router;
