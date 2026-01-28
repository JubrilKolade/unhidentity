const AWS = require('aws-sdk');
const crypto = require('crypto');

const s3 = new AWS.S3({
  endpoint: process.env.S3_ENDPOINT || 'http://localhost:9000',
  accessKeyId: process.env.S3_ACCESS_KEY || 'minioadmin',
  secretAccessKey: process.env.S3_SECRET_KEY || 'minioadmin',
  s3ForcePathStyle: true,
  signatureVersion: 'v4'
});

const BUCKET_NAME = process.env.S3_BUCKET || 'kyc-documents';

class StorageService {
  async upload(key, buffer, contentType) {
    const encryptedBuffer = this.encrypt(buffer);
    
    const params = {
      Bucket: BUCKET_NAME,
      Key: key,
      Body: encryptedBuffer,
      ContentType: contentType,
      ServerSideEncryption: 'AES256'
    };

    await s3.putObject(params).promise();
    return key;
  }

  async download(key) {
    const params = {
      Bucket: BUCKET_NAME,
      Key: key
    };

    const data = await s3.getObject(params).promise();
    return this.decrypt(data.Body);
  }

  async delete(key) {
    const params = {
      Bucket: BUCKET_NAME,
      Key: key
    };

    await s3.deleteObject(params).promise();
  }

  encrypt(buffer) {
    const algorithm = 'aes-256-gcm';
    const key = Buffer.from(process.env.ENCRYPTION_KEY || crypto.randomBytes(32).toString('hex'), 'hex').slice(0, 32);
    const iv = crypto.randomBytes(16);
    
    const cipher = crypto.createCipheriv(algorithm, key, iv);
    const encrypted = Buffer.concat([cipher.update(buffer), cipher.final()]);
    const authTag = cipher.getAuthTag();
    
    return Buffer.concat([iv, authTag, encrypted]);
  }

  decrypt(buffer) {
    const algorithm = 'aes-256-gcm';
    const key = Buffer.from(process.env.ENCRYPTION_KEY || crypto.randomBytes(32).toString('hex'), 'hex').slice(0, 32);
    
    const iv = buffer.slice(0, 16);
    const authTag = buffer.slice(16, 32);
    const encrypted = buffer.slice(32);
    
    const decipher = crypto.createDecipheriv(algorithm, key, iv);
    decipher.setAuthTag(authTag);
    
    return Buffer.concat([decipher.update(encrypted), decipher.final()]);
  }
}

module.exports = new StorageService();