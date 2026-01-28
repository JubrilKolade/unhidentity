require('dotenv').config();
const app = require('./app');
const logger = require('./utils/logger');

// Start webhook retry job
require('./jobs/webhook-retry');

const PORT = process.env.PORT || 3000;

const server = app.listen(PORT, () => {
  logger.info(`UnhIdentity API Gateway running on port ${PORT}`);
  console.log(`✅ Server is running on http://localhost:${PORT}`);
  console.log(`🏥 Health check: http://localhost:${PORT}/health`);
  console.log(`🔄 Webhook retry job started`);
});

process.on('SIGTERM', () => {
  logger.info('SIGTERM signal received: closing HTTP server');
  server.close(() => {
    logger.info('HTTP server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  logger.info('SIGINT signal received: closing HTTP server');
  server.close(() => {
    logger.info('HTTP server closed');
    process.exit(0);
  });
});