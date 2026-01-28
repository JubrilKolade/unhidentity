import { pool } from '../config/database.js';
import queueService from './queue.service.js';
import storageService from '../config/storage.js';
import path from 'path';

class VerificationService {
  async create(data) {
    const client = await pool.connect();
    
    try {
      const query = `
        INSERT INTO verifications (
          customer_id, external_id, first_name, last_name, 
          date_of_birth, metadata, ip_address, user_agent, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
        RETURNING *
      `;

      const values = [
        data.customer_id,
        data.external_id,
        data.first_name,
        data.last_name,
        data.date_of_birth,
        data.metadata || {},
        data.ip_address,
        data.user_agent
      ];

      const result = await client.query(query, values);
      
      await this.createAuditLog(client, {
        verification_id: result.rows[0].id,
        customer_id: data.customer_id,
        action: 'verification_created',
        actor: 'api'
      });

      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async uploadDocuments(verificationId, customerId, { document_type, document_country, front, back }) {
    const client = await pool.connect();

    try {
      const verification = await this.getById(verificationId, customerId);
      if (!verification) {
        throw new Error('Verification not found');
      }

      const frontPath = await this.uploadFile(front, verificationId, 'document_front');
      let backPath = null;
      
      if (back) {
        backPath = await this.uploadFile(back, verificationId, 'document_back');
      }

      const query = `
        UPDATE verifications 
        SET document_type = $1, 
            document_country = $2,
            document_front_path = $3,
            document_back_path = $4,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $5 AND customer_id = $6
        RETURNING *
      `;

      const result = await client.query(query, [
        document_type,
        document_country,
        frontPath,
        backPath,
        verificationId,
        customerId
      ]);

      await this.createAuditLog(client, {
        verification_id: verificationId,
        customer_id: customerId,
        action: 'documents_uploaded',
        actor: 'api'
      });

      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async uploadSelfie(verificationId, customerId, file) {
    const client = await pool.connect();

    try {
      const verification = await this.getById(verificationId, customerId);
      if (!verification) {
        throw new Error('Verification not found');
      }

      const selfiePath = await this.uploadFile(file, verificationId, 'selfie');

      const query = `
        UPDATE verifications 
        SET selfie_path = $1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $2 AND customer_id = $3
        RETURNING *
      `;

      const result = await client.query(query, [selfiePath, verificationId, customerId]);

      await this.createAuditLog(client, {
        verification_id: verificationId,
        customer_id: customerId,
        action: 'selfie_uploaded',
        actor: 'api'
      });

      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async submit(verificationId, customerId) {
    const client = await pool.connect();

    try {
      const verification = await this.getById(verificationId, customerId);
      
      if (!verification) {
        throw new Error('Verification not found');
      }

      if (!verification.document_front_path || !verification.selfie_path) {
        throw new Error('Missing required documents or selfie');
      }

      const query = `
        UPDATE verifications 
        SET status = 'processing',
            submitted_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND customer_id = $2
        RETURNING *
      `;

      const result = await client.query(query, [verificationId, customerId]);

      await queueService.addVerificationJob(result.rows[0]);

      await this.createAuditLog(client, {
        verification_id: verificationId,
        customer_id: customerId,
        action: 'verification_submitted',
        actor: 'api'
      });

      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async getById(verificationId, customerId) {
    const query = `
      SELECT * FROM verifications 
      WHERE id = $1 AND customer_id = $2
    `;
    
    const result = await pool.query(query, [verificationId, customerId]);
    return result.rows[0];
  }

  async list(customerId, { status, limit, offset }) {
    let query = `
      SELECT * FROM verifications 
      WHERE customer_id = $1
    `;
    const values = [customerId];
    let paramCount = 1;

    if (status) {
      paramCount++;
      query += ` AND status = $${paramCount}`;
      values.push(status);
    }

    query += ` ORDER BY created_at DESC LIMIT $${paramCount + 1} OFFSET $${paramCount + 2}`;
    values.push(limit, offset);

    const result = await pool.query(query, values);
    return result.rows;
  }

  async uploadFile(file, verificationId, fileType) {
    const fileExt = path.extname(file.originalname);
    const fileName = `${verificationId}/${fileType}_${Date.now()}${fileExt}`;
    
    await storageService.upload(fileName, file.buffer, file.mimetype);
    
    return fileName;
  }

  async createAuditLog(client, { verification_id, customer_id, action, actor, details = {} }) {
    const query = `
      INSERT INTO audit_logs (verification_id, customer_id, action, actor, details)
      VALUES ($1, $2, $3, $4, $5)
    `;
    
    await client.query(query, [verification_id, customer_id, action, actor, details]);
  }
}

export default new VerificationService();
