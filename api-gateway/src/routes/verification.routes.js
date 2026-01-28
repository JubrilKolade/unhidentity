const express = require('express');
const router = express.Router();
const verificationController = require('../controllers/verification.controller');
const { authenticateApiKey } = require('../middleware/auth.middleware');
const { uploadDocuments } = require('../middleware/upload.middleware');

router.use(authenticateApiKey);

router.post('/', verificationController.createVerification);
router.post('/:id/documents', uploadDocuments, verificationController.uploadDocuments);
router.post('/:id/selfie', uploadDocuments, verificationController.uploadSelfie);
router.post('/:id/submit', verificationController.submitVerification);
router.get('/:id', verificationController.getVerification);
router.get('/', verificationController.listVerifications);

module.exports = router;