# Quick Start Guide

## Prerequisites
- Docker & Docker Compose installed
- 4GB RAM minimum
- 10GB disk space

## Installation (5 minutes)

### Step 1: Run Setup
```bash
chmod +x setup.sh
./setup.sh
```

This will:
- ✅ Create environment files
- ✅ Build containers
- ✅ Start all services
- ✅ Create MinIO bucket

### Step 2: Verify Installation
```bash
curl http://localhost:3000/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "unhidentity-api",
  "timestamp": "2025-01-29T..."
}
```

### Step 3: Create First Verification
```bash
curl -X POST http://localhost:3000/api/v1/verifications \
  -H "X-API-Key: test_api_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-01"
  }'
```

Save the `id` from the response.

### Step 4: Upload Documents
```bash
# Upload ID document
curl -X POST http://localhost:3000/api/v1/verifications/{ID}/documents \
  -H "X-API-Key: test_api_key_12345" \
  -F "front=@path/to/id-front.jpg" \
  -F "document_type=passport"

# Upload selfie
curl -X POST http://localhost:3000/api/v1/verifications/{ID}/selfie \
  -H "X-API-Key: test_api_key_12345" \
  -F "selfie=@path/to/selfie.jpg"
```

### Step 5: Submit for Verification
```bash
curl -X POST http://localhost:3000/api/v1/verifications/{ID}/submit \
  -H "X-API-Key: test_api_key_12345"
```

### Step 6: Check Results
```bash
curl http://localhost:3000/api/v1/verifications/{ID} \
  -H "X-API-Key: test_api_key_12345"
```

## Troubleshooting

### Services won't start
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Can't access MinIO
1. Go to http://localhost:9001
2. Login: minioadmin / minioadmin
3. Create bucket: `kyc-documents`

### Database connection errors
```bash
docker-compose restart postgres
docker-compose logs postgres
```

## Next Steps

- Read full API docs in README.md
- Configure webhooks for your application
- Set up production environment variables
- Enable SSL/TLS for production
- Configure backup strategy

## Support

For issues, check logs:
```bash
docker-compose logs -f
```