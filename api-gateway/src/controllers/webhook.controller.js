const webhookService = require('../services/webhook.service');
const { pool } = require('../config/database');
const logger = require('../utils/logger');

class WebhookController {
  async getWebhookHistory(req, res, next) {
    try {
      const { verification_id } = req.query;
      
      const history = await webhookService.getWebhookHistory(
        req.customer.id,
        verification_id
      );

      res.json({
        success: true,
        data: history
      });
    } catch (error) {
      next(error);
    }
  }

  async retryWebhook(req, res, next) {
    try {
      const { id } = req.params;

      // Get webhook delivery
      const query = `
        SELECT wd.*, v.*
        FROM webhook_deliveries wd
        JOIN verifications v ON wd.verification_id = v.id
        WHERE wd.id = $1 AND wd.customer_id = $2
      `;
      
      const result = await pool.query(query, [id, req.customer.id]);

      if (result.rows.length === 0) {
        return res.status(404).json({
          success: false,
          error: 'Webhook delivery not found'
        });
      }

      const row = result.rows[0];

      await webhookService.deliverWebhook({
        id: row.verification_id,
        customer_id: row.customer_id,
        external_id: row.external_id,
        status: row.status,
        risk_level: row.risk_level,
        risk_score: row.risk_score,
        document_verified: row.document_verified,
        face_match_score: row.face_match_score,
        liveness_verified: row.liveness_verified,
        sanctions_check_passed: row.sanctions_check_passed,
        created_at: row.created_at,
        completed_at: row.completed_at
      });

      res.json({
        success: true,
        message: 'Webhook retry initiated'
      });
    } catch (error) {
      next(error);
    }
  }

  async testWebhook(req, res, next) {
    try {
      const payload = {
        event: 'webhook.test',
        message: 'This is a test webhook from UnhIdentity',
        timestamp: new Date().toISOString()
      };

      // Get customer webhook URL
      if (!req.customer.webhook_url) {
        return res.status(400).json({
          success: false,
          error: 'No webhook URL configured'
        });
      }

      const signature = webhookService.generateSignature(payload, req.customer.api_secret);

      const axios = require('axios');
      const response = await axios.post(req.customer.webhook_url, payload, {
        headers: {
          'Content-Type': 'application/json',
          'X-Webhook-Event': 'webhook.test',
          'X-Webhook-Signature': signature,
          'User-Agent': 'UnhIdentity-Webhook/1.0'
        },
        timeout: 10000
      });

      res.json({
        success: true,
        message: 'Test webhook sent successfully',
        response_status: response.status
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: 'Failed to send test webhook',
        details: error.message
      });
    }
  }
}

module.exports = new WebhookController();
