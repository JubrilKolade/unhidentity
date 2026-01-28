const verificationService = require('../services/verification.service');
const logger = require('../utils/logger');

class VerificationController {
  async createVerification(req, res, next) {
    try {
      const { external_id, first_name, last_name, date_of_birth, metadata } = req.body;
      
      const verification = await verificationService.create({
        customer_id: req.customer.id,
        external_id,
        first_name,
        last_name,
        date_of_birth,
        metadata,
        ip_address: req.ip,
        user_agent: req.get('user-agent')
      });

      logger.info(`Verification created: ${verification.id}`);

      res.status(201).json({
        success: true,
        data: verification
      });
    } catch (error) {
      next(error);
    }
  }

  async uploadDocuments(req, res, next) {
    try {
      const { id } = req.params;
      const { document_type, document_country } = req.body;
      const files = req.files;

      if (!files || (!files.front && !files.document)) {
        return res.status(400).json({
          success: false,
          error: 'Document file is required'
        });
      }

      const verification = await verificationService.uploadDocuments(
        id,
        req.customer.id,
        {
          document_type,
          document_country,
          front: files.front ? files.front[0] : files.document[0],
          back: files.back ? files.back[0] : null
        }
      );

      res.json({
        success: true,
        data: verification
      });
    } catch (error) {
      next(error);
    }
  }

  async uploadSelfie(req, res, next) {
    try {
      const { id } = req.params;
      const file = req.files.selfie ? req.files.selfie[0] : null;

      if (!file) {
        return res.status(400).json({
          success: false,
          error: 'Selfie file is required'
        });
      }

      const verification = await verificationService.uploadSelfie(
        id,
        req.customer.id,
        file
      );

      res.json({
        success: true,
        data: verification
      });
    } catch (error) {
      next(error);
    }
  }

  async submitVerification(req, res, next) {
    try {
      const { id } = req.params;
      const verification = await verificationService.submit(id, req.customer.id);

      res.json({
        success: true,
        data: verification,
        message: 'Verification submitted for processing'
      });
    } catch (error) {
      next(error);
    }
  }

  async getVerification(req, res, next) {
    try {
      const { id } = req.params;
      const verification = await verificationService.getById(id, req.customer.id);

      if (!verification) {
        return res.status(404).json({
          success: false,
          error: 'Verification not found'
        });
      }

      res.json({
        success: true,
        data: verification
      });
    } catch (error) {
      next(error);
    }
  }

  async listVerifications(req, res, next) {
    try {
      const { status, limit = 50, offset = 0 } = req.query;

      const verifications = await verificationService.list(req.customer.id, {
        status,
        limit: parseInt(limit),
        offset: parseInt(offset)
      });

      res.json({
        success: true,
        data: verifications
      });
    } catch (error) {
      next(error);
    }
  }
}

module.exports = new VerificationController();