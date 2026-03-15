-- NewsGT Database Schema v1
-- All 9 category domains enforced at DB level

-- ── Source Profiles ───────────────────────────────────────────────────────────
CREATE TABLE source_profiles (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 TEXT NOT NULL UNIQUE,
    status               TEXT NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'inactive', 'defunct')),
    mbfc_credibility     TEXT CHECK (mbfc_credibility IN ('Very High', 'High', 'Mixed', 'Low')),
    credibility_weight   FLOAT CHECK (credibility_weight IN (1.0, 0.8, 0.4, 0.2)),
    manual_bias_profiles JSONB DEFAULT '{}',
    pattern_threshold    JSONB DEFAULT '{}',
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at on source_profiles
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER source_profiles_updated_at
    BEFORE UPDATE ON source_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Stories ───────────────────────────────────────────────────────────────────
CREATE TABLE stories (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gdelt_cluster_id TEXT,
    category_label   TEXT NOT NULL CHECK (category_label IN (
                         'Middle East & Gulf',
                         'US Politics & Foreign Policy',
                         'Russia / Ukraine / NATO',
                         'China / Taiwan / Indo-Pacific',
                         'Global Economy & Trade Wars',
                         'South Asia',
                         'Africa & Resources',
                         'Technology & AI Power',
                         'Climate & Energy Transition'
                     )),
    headline         TEXT,
    timestamp        TIMESTAMPTZ,
    master_fact_set  JSONB DEFAULT '{}',
    master_version   INTEGER DEFAULT 0,
    master_frozen_at TIMESTAMPTZ,
    thread_id        UUID REFERENCES stories(id),
    thread_sequence  INTEGER,
    is_thread_root   BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── Articles ──────────────────────────────────────────────────────────────────
CREATE TABLE articles (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id        UUID REFERENCES source_profiles(id),
    story_id         UUID REFERENCES stories(id),
    gdelt_cluster_id TEXT,
    raw_text         TEXT,
    url              TEXT,
    published_at     TIMESTAMPTZ,
    language         TEXT DEFAULT 'en',
    processed        BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── Article Extractions ───────────────────────────────────────────────────────
CREATE TABLE article_extractions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id     UUID REFERENCES articles(id),
    source_id      UUID REFERENCES source_profiles(id),
    story_id       UUID REFERENCES stories(id),
    who            JSONB DEFAULT '{}',
    what           TEXT,
    when_text      TEXT,
    where_text     TEXT,
    why            TEXT,
    how            TEXT,
    raw_extraction JSONB DEFAULT '{}',
    master_version INTEGER DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── Behavioral Records ────────────────────────────────────────────────────────
CREATE TABLE behavioral_records (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id        UUID REFERENCES source_profiles(id),
    story_id         UUID REFERENCES stories(id),
    category_label   TEXT NOT NULL CHECK (category_label IN (
                         'Middle East & Gulf',
                         'US Politics & Foreign Policy',
                         'Russia / Ukraine / NATO',
                         'China / Taiwan / Indo-Pacific',
                         'Global Economy & Trade Wars',
                         'South Asia',
                         'Africa & Resources',
                         'Technology & AI Power',
                         'Climate & Energy Transition'
                     )),
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    recency_weight   FLOAT DEFAULT 1.0,
    master_version   INTEGER DEFAULT 0,
    selection_score  FLOAT,
    omission_profile JSONB DEFAULT '{}',
    framing_scores   JSONB DEFAULT '{}',
    language_tone    JSONB DEFAULT '{}',
    sourcing_profile JSONB DEFAULT '{}',
    divergence_flag  BOOLEAN DEFAULT FALSE,
    divergence_detail TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── Claims ────────────────────────────────────────────────────────────────────
CREATE TABLE claims (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id               UUID REFERENCES stories(id),
    claim_text             TEXT NOT NULL,
    sources_reporting      JSONB DEFAULT '[]',
    source_agenda_positions JSONB DEFAULT '{}',
    confidence_score       FLOAT CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    confidence_label       TEXT CHECK (confidence_label IN (
                               'ESTABLISHED', 'PROBABLE', 'ASSESSED', 'SPECULATIVE'
                           )),
    agenda_poles_covered   JSONB DEFAULT '[]',
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ── Financial Snapshots ───────────────────────────────────────────────────────
CREATE TABLE financial_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id            UUID REFERENCES stories(id),
    metric_name         TEXT NOT NULL,
    metric_description  TEXT,
    api_source          TEXT CHECK (api_source IN (
                            'FRED', 'yfinance', 'WorldBank', 'IMF', 'AlphaVantage'
                        )),
    ticker_or_series_id TEXT,
    value               FLOAT,
    unit                TEXT,
    timestamp_fetched   TIMESTAMPTZ DEFAULT NOW(),
    relevance_note      TEXT,
    available           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Layer Outputs ─────────────────────────────────────────────────────────────
CREATE TABLE layer_outputs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id          UUID REFERENCES stories(id),
    layer             TEXT NOT NULL CHECK (layer IN ('WHO', 'HOW', 'WHY')),
    content           JSONB DEFAULT '{}',
    confidence_overall TEXT CHECK (confidence_overall IN (
                          'ESTABLISHED', 'PROBABLE', 'ASSESSED', 'SPECULATIVE'
                      )),
    generated_at      TIMESTAMPTZ DEFAULT NOW(),
    model_used        TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── Category Edges (Phase 3) ──────────────────────────────────────────────────
CREATE TABLE category_edges (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_a            TEXT NOT NULL,
    node_b            TEXT NOT NULL,
    weight            FLOAT DEFAULT 0.0,
    weight_history    JSONB DEFAULT '[]',
    last_recalculated TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(node_a, node_b)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX idx_articles_story_id          ON articles(story_id);
CREATE INDEX idx_articles_source_id         ON articles(source_id);
CREATE INDEX idx_articles_processed         ON articles(processed);
CREATE INDEX idx_behavioral_source_story    ON behavioral_records(source_id, story_id);
CREATE INDEX idx_behavioral_category        ON behavioral_records(category_label);
CREATE INDEX idx_claims_story_id            ON claims(story_id);
CREATE INDEX idx_layer_outputs_story_layer  ON layer_outputs(story_id, layer);
CREATE INDEX idx_stories_thread_id          ON stories(thread_id);
CREATE INDEX idx_stories_category           ON stories(category_label);
CREATE INDEX idx_financial_story_id         ON financial_snapshots(story_id);
CREATE INDEX idx_article_extractions_story  ON article_extractions(story_id);
CREATE INDEX idx_article_extractions_source ON article_extractions(source_id);