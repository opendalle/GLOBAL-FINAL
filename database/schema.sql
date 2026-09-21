-- ============================================================
-- NEXUS PROP INTEL v3 — Global CRE Intelligence Terminal
-- Run this entire file in Supabase SQL Editor FIRST
-- ============================================================

CREATE TABLE IF NOT EXISTS companies (
    company_id      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_name    TEXT NOT NULL,
    normalized_name TEXT UNIQUE,
    industry        TEXT,
    website         TEXT,
    hq_location     TEXT,
    country         TEXT DEFAULT 'India',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id      UUID REFERENCES companies(company_id) ON DELETE CASCADE,
    signal_type     TEXT NOT NULL,
    space_type      TEXT,
    location        TEXT,
    country         TEXT DEFAULT 'India',
    region          TEXT DEFAULT 'India',
    confidence_score NUMERIC(5,2),
    urgency         TEXT DEFAULT 'MEDIUM',
    summary         TEXT,
    why_cre         TEXT,
    source_url      TEXT,
    data_source     TEXT,
    published_at    TIMESTAMPTZ,
    funding_amount  TEXT,
    funding_round   TEXT,
    headcount       INTEGER,
    sqft            INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_scores (
    company_id      UUID REFERENCES companies(company_id) ON DELETE CASCADE PRIMARY KEY,
    score           INTEGER DEFAULT 0,
    signal_count    INTEGER DEFAULT 0,
    priority_level  TEXT DEFAULT 'LOW',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_signals_company    ON signals(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_type       ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_country    ON signals(country);
CREATE INDEX IF NOT EXISTS idx_signals_created    ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_source_url ON signals(source_url);
CREATE INDEX IF NOT EXISTS idx_signals_confidence ON signals(confidence_score DESC);

-- Full-text search
ALTER TABLE signals ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(signal_type,'') || ' ' ||
            coalesce(location,'') || ' ' ||
            coalesce(summary,'') || ' ' ||
            coalesce(why_cre,'')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS signals_fts_idx ON signals USING GIN(fts);

ALTER TABLE companies ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(company_name,'') || ' ' ||
            coalesce(industry,'') || ' ' ||
            coalesce(hq_location,'')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS companies_fts_idx ON companies USING GIN(fts);

-- RLS
ALTER TABLE companies   ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals     ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_scores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_read_companies" ON companies;
DROP POLICY IF EXISTS "anon_read_signals" ON signals;
DROP POLICY IF EXISTS "anon_read_lead_scores" ON lead_scores;

CREATE POLICY "anon_read_companies"   ON companies    FOR SELECT USING (true);
CREATE POLICY "anon_read_signals"     ON signals      FOR SELECT USING (true);
CREATE POLICY "anon_read_lead_scores" ON lead_scores  FOR SELECT USING (true);

CREATE POLICY "anon_read_companies"   ON companies    FOR SELECT USING (true);
CREATE POLICY "anon_read_signals"     ON signals      FOR SELECT USING (true);
CREATE POLICY "anon_read_lead_scores" ON lead_scores  FOR SELECT USING (true);

-- ============================================================
-- Schema complete. Run main.py next.
-- ============================================================
