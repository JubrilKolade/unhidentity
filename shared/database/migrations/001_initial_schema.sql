-- UnhIdentity KYC Database Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    api_secret VARCHAR(255) NOT NULL,
    webhook_url VARCHAR(512),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID REFERENCES customers(id),
    external_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    verification_type VARCHAR(50) NOT NULL DEFAULT 'individual',
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    date_of_birth DATE,
    nationality VARCHAR(3),
    document_type VARCHAR(50),
    document_number VARCHAR(255),
    document_country VARCHAR(3),
    document_verified BOOLEAN,
    face_match_score DECIMAL(5,2),
    liveness_verified BOOLEAN,
    sanctions_check_passed BOOLEAN,
    risk_score INTEGER,
    risk_level VARCHAR(20),
    document_front_path VARCHAR(512),
    document_back_path VARCHAR(512),
    selfie_path VARCHAR(512),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    submitted_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'manual_review'))
);

CREATE INDEX idx_verifications_customer_id ON verifications(customer_id);
CREATE INDEX idx_verifications_status ON verifications(status);
CREATE INDEX idx_verifications_created_at ON verifications(created_at);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_id UUID REFERENCES verifications(id),
    customer_id UUID REFERENCES customers(id),
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(100),
    details JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_verification_id ON audit_logs(verification_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_id UUID REFERENCES verifications(id),
    customer_id UUID REFERENCES customers(id),
    url VARCHAR(512) NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    attempt_count INTEGER DEFAULT 1,
    next_retry_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_webhook_deliveries_verification_id ON webhook_deliveries(verification_id);
CREATE INDEX idx_webhook_deliveries_next_retry ON webhook_deliveries(next_retry_at) WHERE delivered_at IS NULL;

CREATE TABLE sanctions_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    list_name VARCHAR(100) NOT NULL,
    entry_type VARCHAR(50),
    name VARCHAR(500) NOT NULL,
    aliases TEXT[],
    date_of_birth DATE,
    nationality VARCHAR(3),
    identifiers JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_vector tsvector
);

CREATE INDEX idx_sanctions_name ON sanctions_entries USING gin(search_vector);
CREATE INDEX idx_sanctions_list_name ON sanctions_entries(list_name);

CREATE OR REPLACE FUNCTION sanctions_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := to_tsvector('english', NEW.name);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER sanctions_search_update BEFORE INSERT OR UPDATE
ON sanctions_entries FOR EACH ROW EXECUTE FUNCTION sanctions_search_trigger();

INSERT INTO customers (name, email, api_key, api_secret, webhook_url, is_active)
VALUES (
    'Test Company',
    'test@unhidentity.com',
    'test_api_key_12345',
    'test_secret_67890',
    'https://webhook.site/unique-url-here',
    true
);