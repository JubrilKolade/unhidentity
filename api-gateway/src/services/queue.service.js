const { redis } = require('../config/redis');

class QueueService {
  constructor() {
    this.stream = 'verification-processing';
    this.group = 'verification_group';
    this.ensureStreamGroup();
  }

  async ensureStreamGroup() {
    try {
      await redis.xgroup('CREATE', this.stream, this.group, '$', 'MKSTREAM');
    } catch (err) {
      const msg = String(err && err.message || '');
      if (!msg.includes('BUSYGROUP')) {
        console.error('Stream group error:', err);
      }
    }
  }

  async addVerificationJob(verification) {
    const payload = {
      verification_id: verification.id,
      customer_id: verification.customer_id,
      document_front_path: verification.document_front_path,
      document_back_path: verification.document_back_path,
      selfie_path: verification.selfie_path,
      document_type: verification.document_type,
      first_name: verification.first_name,
      last_name: verification.last_name,
      date_of_birth: verification.date_of_birth
    };
    const id = await redis.xadd(
      this.stream,
      '*',
      'type',
      'process-verification',
      'data',
      JSON.stringify(payload)
    );
    return id;
  }
}

module.exports = new QueueService();
