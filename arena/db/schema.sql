-- ============================================================
-- The Fifty Fund Arena — PostgreSQL Schema
-- Run once on a fresh Railway PostgreSQL instance
-- ============================================================

-- ── FUNDS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funds (
    id               SERIAL PRIMARY KEY,
    slug             VARCHAR(50)  UNIQUE NOT NULL,
    name             VARCHAR(100) NOT NULL,
    model            VARCHAR(100) NOT NULL,
    provider         VARCHAR(50)  NOT NULL,
    strategy         VARCHAR(100) NOT NULL,
    personality      TEXT,
    starting_balance NUMERIC(10,4) NOT NULL DEFAULT 50.0000,
    current_balance  NUMERIC(10,4) NOT NULL DEFAULT 50.0000,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TRADES ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id          SERIAL PRIMARY KEY,
    fund_id     INTEGER NOT NULL REFERENCES funds(id),
    cycle_id    VARCHAR(100),
    symbol      VARCHAR(10) NOT NULL,
    action      VARCHAR(10) NOT NULL CHECK (action IN ('BUY','SELL','HOLD')),
    shares      NUMERIC(12,6) DEFAULT 0,
    price       NUMERIC(12,4) DEFAULT 0,
    reasoning   TEXT,
    paper       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── POSITIONS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id            SERIAL PRIMARY KEY,
    fund_id       INTEGER NOT NULL REFERENCES funds(id),
    symbol        VARCHAR(10) NOT NULL,
    shares        NUMERIC(12,6) NOT NULL DEFAULT 0,
    avg_price     NUMERIC(12,4) NOT NULL DEFAULT 0,
    current_price NUMERIC(12,4),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(fund_id, symbol)
);

-- ── ROASTS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roasts (
    id         SERIAL PRIMARY KEY,
    fund_id    INTEGER NOT NULL REFERENCES funds(id),
    roast_date DATE NOT NULL,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(fund_id, roast_date)
);

-- ── SOCIAL STATS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_stats (
    id              SERIAL PRIMARY KEY,
    stat_date       DATE NOT NULL UNIQUE,
    x_followers     INTEGER DEFAULT 0,
    x_impressions   INTEGER DEFAULT 0,
    substack_subs   INTEGER DEFAULT 0,
    paid_subs       INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── EDITIONS (Tribune archive) ───────────────────────────────
CREATE TABLE IF NOT EXISTS editions (
    id           SERIAL PRIMARY KEY,
    edition_date DATE NOT NULL UNIQUE,
    headline     TEXT,
    file_path    VARCHAR(255),
    published_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── SEED DATA ────────────────────────────────────────────────
INSERT INTO funds (slug, name, model, provider, strategy, personality) VALUES
('algomind',      'AlgoMind',       'claude-sonnet-4-6',   'anthropic', 'Momentum + Technical',      'Precise, dry, slightly smug. Confirms before committing.'),
('oracle',        'Oracle',         'gpt-4o',              'openai',    'Macro + Sentiment',          'Overconfident, always has a take. Speaks in pronouncements.'),
('gemini_rising', 'Gemini Rising',  'gemini-2.5-pro',      'google',    'Sector Rotation + Macro',    'Optimistic, data-heavy, occasionally blindsided.'),
('maverick',      'Maverick',       'grok-4-1-fast',       'xai',       'Contrarian + Mean Reversion','Unpredictable, unfiltered, loves the underdog play.'),
('dragon',        'Dragon',         'deepseek-chat',       'deepseek',  'Quantitative + High Freq',   'Minimal words, maximum math. The dark horse.')
ON CONFLICT (slug) DO NOTHING;

-- ── INDEXES ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_trades_fund_id ON trades(fund_id);
CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_positions_fund ON positions(fund_id);
CREATE INDEX IF NOT EXISTS idx_roasts_date ON roasts(roast_date);
