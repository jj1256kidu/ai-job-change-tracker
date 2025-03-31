-- Create the database if it doesn't exist
CREATE DATABASE job_changes;

-- Connect to the database
\c job_changes;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create tables
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    linkedin_url VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_changes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    old_position VARCHAR(255),
    new_position VARCHAR(255) NOT NULL,
    change_date TIMESTAMP WITH TIME ZONE NOT NULL,
    profile_url VARCHAR(255) NOT NULL,
    is_new BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(is_active);
CREATE INDEX IF NOT EXISTS idx_job_changes_company ON job_changes(company);
CREATE INDEX IF NOT EXISTS idx_job_changes_name ON job_changes(name);
CREATE INDEX IF NOT EXISTS idx_job_changes_change_date ON job_changes(change_date);
CREATE INDEX IF NOT EXISTS idx_job_changes_is_new ON job_changes(is_new);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_changes_updated_at
    BEFORE UPDATE ON job_changes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert initial companies
INSERT INTO companies (name, linkedin_url) VALUES
    ('TCS', 'https://www.linkedin.com/company/tata-consultancy-services'),
    ('Infosys', 'https://www.linkedin.com/company/infosys'),
    ('Wipro', 'https://www.linkedin.com/company/wipro'),
    ('HCL', 'https://www.linkedin.com/company/hcl-technologies'),
    ('Tech Mahindra', 'https://www.linkedin.com/company/tech-mahindra'),
    ('Accenture', 'https://www.linkedin.com/company/accenture'),
    ('IBM', 'https://www.linkedin.com/company/ibm'),
    ('Microsoft', 'https://www.linkedin.com/company/microsoft'),
    ('Google', 'https://www.linkedin.com/company/google'),
    ('Amazon', 'https://www.linkedin.com/company/amazon')
ON CONFLICT (name) DO NOTHING;

-- Create views for common queries
CREATE OR REPLACE VIEW v_recent_changes AS
SELECT 
    jc.*,
    c.linkedin_url as company_linkedin_url
FROM job_changes jc
JOIN companies c ON jc.company = c.name
WHERE jc.is_new = true
ORDER BY jc.change_date DESC;

CREATE OR REPLACE VIEW v_company_stats AS
SELECT 
    c.name,
    c.linkedin_url,
    COUNT(jc.id) as total_changes,
    COUNT(DISTINCT jc.name) as unique_people,
    MAX(jc.change_date) as last_change_date
FROM companies c
LEFT JOIN job_changes jc ON c.name = jc.company
WHERE c.is_active = true
GROUP BY c.name, c.linkedin_url;

-- Create function to get changes by date range
CREATE OR REPLACE FUNCTION get_changes_by_date_range(
    p_start_date TIMESTAMP WITH TIME ZONE,
    p_end_date TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
    company_name VARCHAR,
    total_changes BIGINT,
    unique_people BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        jc.company as company_name,
        COUNT(*) as total_changes,
        COUNT(DISTINCT jc.name) as unique_people
    FROM job_changes jc
    WHERE jc.change_date BETWEEN p_start_date AND p_end_date
    GROUP BY jc.company
    ORDER BY total_changes DESC;
END;
$$ LANGUAGE plpgsql;

-- Create function to get company trends
CREATE OR REPLACE FUNCTION get_company_trends(
    p_company VARCHAR,
    p_days INTEGER
)
RETURNS TABLE (
    change_date DATE,
    daily_changes BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        jc.change_date::DATE,
        COUNT(*) as daily_changes
    FROM job_changes jc
    WHERE jc.company = p_company
    AND jc.change_date >= CURRENT_DATE - (p_days || ' days')::INTERVAL
    GROUP BY jc.change_date::DATE
    ORDER BY change_date;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for the views
CREATE INDEX IF NOT EXISTS idx_v_recent_changes_change_date ON v_recent_changes(change_date);
CREATE INDEX IF NOT EXISTS idx_v_company_stats_name ON v_company_stats(name);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE job_changes TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL VIEWS IN SCHEMA public TO postgres; 