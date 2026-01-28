import { pool } from '../config/database.js';

const authenticateApiKey = async (req, res, next) => {
  try {
    const apiKey = req.headers['x-api-key'];
    
    if (!apiKey) {
      return res.status(401).json({
        success: false,
        error: 'API key is required'
      });
    }

    const query = 'SELECT * FROM customers WHERE api_key = $1 AND is_active = true';
    const result = await pool.query(query, [apiKey]);

    if (result.rows.length === 0) {
      return res.status(401).json({
        success: false,
        error: 'Invalid API key'
      });
    }

    req.customer = result.rows[0];
    next();
  } catch (error) {
    next(error);
  }
};

export { authenticateApiKey };
