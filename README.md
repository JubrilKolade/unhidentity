# UnhIdentity - KYC as a Service

A comprehensive Know Your Customer (KYC) verification service built with Node.js and Python.

## Features

- 📄 Document Verification (OCR, MRZ parsing, authenticity checks)
- 😊 Face Matching (Biometric verification with liveness detection)
- 🔍 Sanctions Screening (Check against global watchlists)
- 🔐 Secure Storage (Encrypted document storage)
- 📊 Risk Scoring (Automated risk assessment)
- 🔔 Webhooks (Real-time status notifications)
- 📝 Audit Trails (Complete verification history)

## Quick Start
```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:3000/health

# View logs
docker-compose logs -f
```

## Access Points

- **API Gateway**: http://localhost:3000
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **Test API Key**: `test_api_key_12345`

## API Usage

### 1. Create Verification
```bash
curl -X POST http://localhost:3000/api/v1/verifications \
  -H "X-API-Key: test_api_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "user_123",
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-01"
  }'
```

### 2. Upload Document
```bash
curl -X POST http://localhost:3000/api/v1/verifications/{id}/documents \
  -H "X-API-Key: test_api_key_12345" \
  -F "front=@/path/to/id.jpg" \
  -F "document_type=passport" \
  -F "document_country=USA"
```

### 3. Upload Selfie
```bash
curl -X POST http://localhost:3000/api/v1/verifications/{id}/selfie \
  -H "X-API-Key: test_api_key_12345" \
  -F "selfie=@/path/to/selfie.jpg"
```

### 4. Submit for Processing
```bash
curl -X POST http://localhost:3000/api/v1/verifications/{id}/submit \
  -H "X-API-Key: test_api_key_12345"
```

### 5. Check Status
```bash
curl http://localhost:3000/api/v1/verifications/{id} \
  -H "X-API-Key: test_api_key_12345"
```

## Development
```bash
# Install dependencies
cd api-gateway && npm install
cd ../worker-service && pip install -r requirements.txt

# Start database only
docker-compose up postgres redis minio -d

# Run API locally
cd api-gateway && npm run dev

# Run worker locally
cd worker-service && python main.py
```

## License

MIT

