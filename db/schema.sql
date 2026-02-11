PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Users table (optional, helpful for joins / bookkeeping)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Persistent user states (encrypted application-layer payload)
CREATE TABLE IF NOT EXISTS user_states (
    telegram_id INTEGER UNIQUE NOT NULL,
    state TEXT,
    data BLOB, -- encrypted JSON
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_states_telegram_id ON user_states(telegram_id);

-- Stored natal charts (encrypted binary blob / JSON)
CREATE TABLE IF NOT EXISTS charts (
    telegram_id INTEGER UNIQUE NOT NULL,
    chart_blob BLOB, -- encrypted serialized chart
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Payments / invoices table (minimal)
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    provider_invoice_id TEXT,
    status TEXT,
    payload BLOB,
    created_at TEXT DEFAULT (datetime('now'))
);
