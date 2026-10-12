PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS requests (
    request_id INTEGER PRIMARY KEY,
    endpoint TEXT NOT NULL,
    params_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    http_status INTEGER,
    error_code INTEGER,
    raw_path TEXT,
    raw_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS catalog (
    market_hash_name TEXT PRIMARY KEY,
    name_zh TEXT,
    category TEXT NOT NULL,
    weapon TEXT,
    skin TEXT,
    quality TEXT,
    exterior TEXT,
    family TEXT,
    steamdt_item_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    source_request INTEGER REFERENCES requests(request_id),
    metadata_request INTEGER REFERENCES requests(request_id),
    styles_checked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS catalog_query ON catalog(category, weapon, exterior, quality);
CREATE INDEX IF NOT EXISTS catalog_id ON catalog(steamdt_item_id);
CREATE INDEX IF NOT EXISTS catalog_family ON catalog(family);
CREATE TABLE IF NOT EXISTS platform_ids (
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    platform TEXT NOT NULL,
    platform_item_id TEXT NOT NULL,
    PRIMARY KEY(market_hash_name, platform)
);
CREATE TABLE IF NOT EXISTS styles (
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    style TEXT NOT NULL,
    name TEXT,
    source_request INTEGER REFERENCES requests(request_id),
    PRIMARY KEY(market_hash_name, style)
);
CREATE TABLE IF NOT EXISTS trades (
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    source_trade_id TEXT NOT NULL,
    platform_code TEXT NOT NULL,
    trade_time INTEGER NOT NULL,
    price_cny TEXT NOT NULL,
    trade_num INTEGER,
    paint_index INTEGER,
    paint_seed INTEGER,
    wear_decimal TEXT,
    wear_value REAL,
    min_sell_price_cny TEXT,
    special_style_json TEXT,
    stickers_json TEXT,
    source_request INTEGER NOT NULL REFERENCES requests(request_id),
    last_request INTEGER NOT NULL REFERENCES requests(request_id),
    PRIMARY KEY(market_hash_name, source_trade_id)
);
CREATE INDEX IF NOT EXISTS trades_time ON trades(market_hash_name, trade_time);
CREATE INDEX IF NOT EXISTS trades_float ON trades(market_hash_name, wear_value, paint_seed);
CREATE TABLE IF NOT EXISTS bars (
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    platform TEXT NOT NULL,
    period TEXT NOT NULL,
    style TEXT NOT NULL DEFAULT '',
    source_time INTEGER NOT NULL,
    bucket_time INTEGER NOT NULL,
    open_cny TEXT NOT NULL,
    close_cny TEXT NOT NULL,
    high_cny TEXT NOT NULL,
    low_cny TEXT NOT NULL,
    source_volume INTEGER,
    source_turnover_cny TEXT,
    source_request INTEGER NOT NULL REFERENCES requests(request_id),
    PRIMARY KEY(market_hash_name, platform, period, style, source_time)
);
CREATE INDEX IF NOT EXISTS bars_time ON bars(market_hash_name, period, platform, style, bucket_time);
CREATE TABLE IF NOT EXISTS snapshots (
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    request_id INTEGER NOT NULL REFERENCES requests(request_id),
    source_json TEXT NOT NULL,
    PRIMARY KEY(market_hash_name, request_id)
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY,
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    kind TEXT NOT NULL CHECK(kind IN ('trades','bars')),
    platform TEXT NOT NULL DEFAULT 'ALL',
    period TEXT NOT NULL DEFAULT '1h',
    style TEXT NOT NULL DEFAULT '',
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    cursor TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','done','blocked')),
    pages INTEGER NOT NULL DEFAULT 0,
    fetched_rows INTEGER NOT NULL DEFAULT 0,
    inserted_rows INTEGER NOT NULL DEFAULT 0,
    min_time INTEGER,
    max_time INTEGER,
    finish_reason TEXT,
    last_error TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(market_hash_name, kind, platform, period, style, start_time, end_time),
    CHECK(start_time < end_time)
);
CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state, priority, pages, job_id);
CREATE TABLE IF NOT EXISTS checkpoints (
    job_id INTEGER NOT NULL REFERENCES jobs(job_id),
    cursor TEXT NOT NULL,
    request_id INTEGER NOT NULL REFERENCES requests(request_id),
    PRIMARY KEY(job_id, cursor)
);
CREATE TABLE IF NOT EXISTS universes (
    universe_id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    scope TEXT NOT NULL,
    profile_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS universe_members (
    universe_id TEXT NOT NULL REFERENCES universes(universe_id),
    market_hash_name TEXT NOT NULL REFERENCES catalog(market_hash_name),
    role TEXT NOT NULL CHECK(role IN ('selected','reserve','rejected')),
    rank_order INTEGER NOT NULL,
    selection_score REAL,
    price_cny TEXT,
    source_supply INTEGER,
    known_7d_volume INTEGER,
    source_heat_rank INTEGER,
    metrics_json TEXT NOT NULL,
    PRIMARY KEY(universe_id,market_hash_name)
);
