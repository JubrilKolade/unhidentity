const { pool } = require('../config/database');
const axios = require('axios');
const crypto = require('crypto');
const logger = require('../utils/logger');

class WebhookService {
  async deliverWebhook(verification, event = 'verification.completed') {
    try {
      // Get customer webhook URL
      const customerQuery = 'SELECT webhook_url, api_secret FROM customers WHERE id = $1';
      const customerResult = await pool.query(customerQuery, [verification.customer_id]);
      
      if (!customerResult.rows[0]?.webhook_url) {
        logger.info(`No webhook URL configured for customer ${verification.customer_id}`);
        return;
      }

      const customer = customerResult.rows[0];
      const webhookUrl = customer.webhook_url;
      
      // Prepare payload
      const payload = {
        event: event,
        verification_id: verification.id,
        external_id: verification.external_id,
        status: verification.status,
        risk_level: verification.risk_level,
        risk_score: verification.risk_score,
        results: {
          document_verified: verification.document_verified,
          face_match_score: parseFloat(verification.face_match_score) || 0,
          liveness_verified: verification.liveness_verified,
          sanctions_check_passed: verification.sanctions_check_passed
        },
        created_at: verification.created_at,
        completed_at: verification.completed_at,
        timestamp: new Date().toISOString()
      };

      // Generate signature for webhook verification
      const signature = this.generateSignature(payload, customer.api_secret);

      // Store webhook attempt
      const insertQuery = `
        INSERT INTO webhook_deliveries (verification_id, customer_id, url, payload, attempt_count)
        VALUES ($1, $2, $3, $4, 1)
        RETURNING id
      `;
      
      const deliveryResult = await pool.query(insertQuery, [
        verification.id,
        verification.customer_id,
        webhookUrl,
        payload
      ]);
      
      const deliveryId = deliveryResult.rows[0].id;

      // Send webhook with retry logic
      await this.sendWebhookWithRetry(deliveryId, webhookUrl, payload, signature);

      logger.info(`Webhook delivered successfully to ${webhookUrl}`);

    } catch (error) {
      logger.error(`Webhook delivery failed: ${error.message}`);
      throw error;
    }
  }

  async sendWebhookWithRetry(deliveryId, url, payload, signature, attempt = 1) {
    const maxAttempts = 3;
    
    try {
      const response = await axios.post(url, payload, {
        headers: {
          'Content-Type': 'application/json',
          'X-Webhook-Event': payload.event,
          'X-Webhook-ID': deliveryId,
          'X-Webhook-Signature': signature,
          'X-Webhook-Timestamp': payload.timestamp,
          'User-Agent': 'UnhIdentity-Webhook/1.0'
        },
        timeout: 15000,
        validateStatus: (status) => status >= 200 && status < 300
      });

      // Mark as delivered
      await pool.query(`
        UPDATE webhook_deliveries 
        SET response_status = $1, 
            response_body = $2, 
            delivered_at = CURRENT_TIMESTAMP,
            attempt_count = $3
        WHERE id = $4
      `, [
        response.status, 
        JSON.stringify(response.data).substring(0, 2000), 
        attempt,
        deliveryId
      ]);

      return true;

    } catch (error) {
      const errorMessage = error.response?.data || error.message;
      const statusCode = error.response?.status || 0;

      // Update delivery record
      await pool.query(`
        UPDATE webhook_deliveries 
        SET response_status = $1, 
            response_body = $2,
            attempt_count = $3,
            next_retry_at = CURRENT_TIMESTAMP + INTERVAL '${this.getRetryDelay(attempt)} minutes'
        WHERE id = $4
      `, [
        statusCode, 
        JSON.stringify(errorMessage).substring(0, 2000),
        attempt,
        deliveryId
      ]);

      // Retry if attempts remain
      if (attempt < maxAttempts) {
        const delay = this.getRetryDelay(attempt) * 60 * 1000; // Convert to milliseconds
        logger.info(`Retrying webhook ${deliveryId} in ${delay / 1000} seconds (attempt ${attempt + 1}/${maxAttempts})`);
        
        await new Promise(resolve => setTimeout(resolve, delay));
        return await this.sendWebhookWithRetry(deliveryId, url, payload, signature, attempt + 1);
      }

      throw error;
    }
  }

  getRetryDelay(attempt) {
    // Exponential backoff: 5, 15, 30 minutes
    const delays = [5, 15, 30];
    return delays[attempt - 1] || 60;
  }

  generateSignature(payload, secret) {
    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(JSON.stringify(payload));
    return hmac.digest('hex');
  }

  async retryFailedWebhooks() {
    try {
      const query = `
        SELECT wd.*, v.* 
        FROM webhook_deliveries wd
        JOIN verifications v ON wd.verification_id = v.id
        WHERE wd.delivered_at IS NULL 
          AND wd.attempt_count < 5 
          AND (wd.next_retry_at IS NULL OR wd.next_retry_at <= CURRENT_TIMESTAMP)
        ORDER BY wd.created_at ASC
        LIMIT 50
      `;
      
      const result = await pool.query(query);
      
      logger.info(`Found ${result.rows.length} failed webhooks to retry`);

      for (const row of result.rows) {
        try {
          await this.deliverWebhook({
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
          }, row.payload.event);
        } catch (error) {
          logger.error(`Failed to retry webhook ${row.id}: ${error.message}`);
        }
      }

      return result.rows.length;
    } catch (error) {
      logger.error(`Error in retryFailedWebhooks: ${error.message}`);
      throw error;
    }
  }

  async getWebhookHistory(customerId, verificationId = null) {
    let query = `
      SELECT wd.*, v.external_id, v.status as verification_status
      FROM webhook_deliveries wd
      JOIN verifications v ON wd.verification_id = v.id
      WHERE wd.customer_id = $1
    `;
    
    const params = [customerId];
    
    if (verificationId) {
      query += ` AND wd.verification_id = $2`;
      params.push(verificationId);
    }
    
    query += ` ORDER BY wd.created_at DESC LIMIT 100`;
    
    const result = await pool.query(query, params);
    return result.rows;
  }
}

module.exports = new WebhookService();