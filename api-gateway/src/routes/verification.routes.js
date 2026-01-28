import express from 'express';
const router = express.Router();
import verificationController from '../controllers/verification.controller.js';
import { authenticateApiKey } from '../middleware/auth.middleware.js';
import { uploadDocuments } from '../middleware/upload.middleware.js';

router.use(authenticateApiKey);

router.post('/', verificationController.createVerification);
router.post('/:id/documents', uploadDocuments, verificationController.uploadDocuments);
router.post('/:id/selfie', uploadDocuments, verificationController.uploadSelfie);
router.post('/:id/submit', verificationController.submitVerification);
router.get('/:id', verificationController.getVerification);
router.get('/', verificationController.listVerifications);

export default router;
