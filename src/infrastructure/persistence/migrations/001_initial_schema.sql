CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    filled_volume INTEGER DEFAULT 0,
    order_type TEXT NOT NULL DEFAULT 'LIMIT',
    status TEXT NOT NULL DEFAULT 'CREATED',
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    commission REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    profit REAL DEFAULT 0,
    traded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    total_asset REAL NOT NULL,
    available_cash REAL NOT NULL,
    market_value REAL NOT NULL,
    pnl REAL DEFAULT 0,
    return_rate REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
    account_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    total_volume INTEGER DEFAULT 0,
    available_volume INTEGER DEFAULT 0,
    average_cost REAL DEFAULT 0,
    PRIMARY KEY (account_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_trades_order ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(date);
