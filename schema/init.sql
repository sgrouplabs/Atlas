-- ================================================================
-- [ARCH] Atlas-MH Rater — Normalized Schema
-- Carriers, Rate Tables, Territory Mapping, Premium Logs
-- ================================================================

CREATE TABLE IF NOT EXISTS carriers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(20) UNIQUE NOT NULL,
    form_complexity VARCHAR(20) DEFAULT 'standard',
    priority        INTEGER DEFAULT 5,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rate_tables (
    id              SERIAL PRIMARY KEY,
    carrier_id      INTEGER REFERENCES carriers(id),
    plan_code       VARCHAR(50),
    base_rate       DECIMAL(10, 4),
    effective_date  DATE,
    expiration_date DATE,
    state           VARCHAR(2),
    raw_json        JSONB,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zip_territory_mapping (
    id              SERIAL PRIMARY KEY,
    zip_code        VARCHAR(10) NOT NULL,
    state           VARCHAR(2),
    county          VARCHAR(100),
    territory_code  VARCHAR(20),
    territory_factor DECIMAL(6, 4),
    carrier_id      INTEGER REFERENCES carriers(id)
);

CREATE TABLE IF NOT EXISTS tier_factors (
    id              SERIAL PRIMARY KEY,
    carrier_id      INTEGER REFERENCES carriers(id),
    tier_code       VARCHAR(20),
    tier_label      VARCHAR(50),
    factor          DECIMAL(6, 4)
);

CREATE TABLE IF NOT EXISTS rate_variables (
    id              SERIAL PRIMARY KEY,
    carrier_id      INTEGER REFERENCES carriers(id),
    variable_key   VARCHAR(50),
    variable_value  DECIMAL(8, 4),
    state           VARCHAR(2)
);

CREATE TABLE IF NOT EXISTS premium_logs (
    id              SERIAL PRIMARY KEY,
    carrier_id      INTEGER REFERENCES carriers(id),
    zip_code        VARCHAR(10),
    base_rate       DECIMAL(10, 4),
    territory_factor DECIMAL(6, 4),
    tier_factor     DECIMAL(6, 4),
    variable_factors JSONB,
    final_premium   DECIMAL(10, 4),
    calculated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rate_tables_carrier ON rate_tables(carrier_id);
CREATE INDEX idx_rate_tables_plan ON rate_tables(plan_code);
CREATE INDEX idx_zip_map_zip ON zip_territory_mapping(zip_code);
CREATE INDEX idx_zip_map_carrier ON zip_territory_mapping(carrier_id);
CREATE INDEX idx_premium_logs_carrier ON premium_logs(carrier_id);

-- Seed carriers
INSERT INTO carriers (name, code, form_complexity, priority) VALUES
    ('Foremost', 'FOREMOST', 'high', 1),
    ('American Modern', 'AMERMOD', 'standard', 2),
    ('Assurant', 'ASSURANT', 'medium', 3),
    ('Tower Hill', 'TOWERHILL', 'medium', 4),
    ('Aegis', 'AEGIS', 'low', 5)
ON CONFLICT (code) DO NOTHING;