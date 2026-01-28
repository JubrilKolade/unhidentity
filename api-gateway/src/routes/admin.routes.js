import express from 'express';
const router = express.Router();

router.get('/stats', (req, res) => {
  res.json({ message: 'Admin stats endpoint - Coming soon' });
});

export default router;
