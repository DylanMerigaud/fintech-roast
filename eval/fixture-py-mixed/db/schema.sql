CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    balance NUMERIC(6,2) NOT NULL DEFAULT 0
);

CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    subtotal DOUBLE PRECISION NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    tax DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    issued_at TIMESTAMP NOT NULL
);

CREATE TABLE invoice_lines (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);

CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    amount DOUBLE PRECISION NOT NULL,
    external_ref TEXT,
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE webhook_events (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    event_type TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    amount DOUBLE PRECISION NOT NULL,
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE ledger_entries (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    amount DOUBLE PRECISION NOT NULL,
    kind TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
