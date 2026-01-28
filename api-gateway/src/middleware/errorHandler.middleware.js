import logger from '../utils/logger.js';

const errorHandler = (err, req, res, next) => {
  logger.error({
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method
  });

  if (err.name === 'MulterError') {
    if (err.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({
        success: false,
        error: 'File size too large. Maximum size is 10MB'
      });
    }
    return res.status(400).json({
      success: false,
      error: err.message
    });
  }

  if (err.name === 'ValidationError') {
    return res.status(400).json({
      success: false,
      error: err.message
    });
  }

  if (err.code && err.code.startsWith('23')) {
    return res.status(400).json({
      success: false,
      error: 'Database validation error'
    });
  }

  res.status(err.status || 500).json({
    success: false,
    error: err.message || 'Internal server error'
  });
};

export { errorHandler };
