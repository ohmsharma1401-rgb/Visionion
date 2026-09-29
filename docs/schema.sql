-- OnionGrade PostgreSQL snapshot schema, for review only.
-- Apply backend/migrations with Alembic; do not execute this on an existing DB.
CREATE TABLE inspections (
  id VARCHAR(36) PRIMARY KEY,
  owner VARCHAR(100) NOT NULL,
  payload TEXT NOT NULL,
  report_hash VARCHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_inspections_owner ON inspections(owner);

CREATE TABLE audit_logs (
  id SERIAL PRIMARY KEY,
  payload TEXT NOT NULL,
  prev_hash VARCHAR(64) NOT NULL,
  hash VARCHAR(64) NOT NULL
);

CREATE TABLE report_artifacts (
  inspection_id VARCHAR(36) PRIMARY KEY,
  pdf_sha256 VARCHAR(64) NOT NULL
);
