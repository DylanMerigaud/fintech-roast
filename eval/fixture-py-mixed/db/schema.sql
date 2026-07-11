-- Billing service schema (Postgres). Mirrors the TypeScript fixture's schema.sql.
-- This is the storage layer the Python service (store.py, ledger.py, webhooks.py)
-- reads and writes, so whatever the columns get wrong quietly spreads to every
-- amount the app moves.

CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    -- STO-2: a running account balance capped at 9999.99, overflows a real balance.
    balance NUMERIC(6,2) NOT NULL DEFAULT 0
    -- STO-4: no currency column, so every balance is a bare number with no unit.
);

CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1: money stored as binary floating point (subtotal, tax, total).
    subtotal DOUBLE PRECISION NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    tax DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    -- TIM-1: a financial instant stored without a time zone.
    issued_at TIMESTAMP NOT NULL
    -- STO-4: still no currency column next to these amounts.
);

CREATE TABLE invoice_lines (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    -- STO-1: a unit price stored as REAL (binary float).
    unit_price REAL NOT NULL
);

CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    -- STO-1: payment amount stored as a double.
    amount DOUBLE PRECISION NOT NULL,
    -- IDE-4: the provider reference has no UNIQUE constraint, so a redelivered
    -- provider event inserts a second payment row for the same external_ref.
    external_ref TEXT,
    -- TIM-1: received_at is a timestamp without time zone.
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE webhook_events (
    id TEXT PRIMARY KEY,
    -- IDE-4: the provider event id has no UNIQUE constraint, so the same event
    -- can be recorded twice and the app-side dedup check has no DB backstop.
    event_id TEXT,
    event_type TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1: the credited amount is a double, and STO-4: no currency alongside.
    amount DOUBLE PRECISION NOT NULL,
    -- TIM-1: received_at is a timestamp without time zone.
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE ledger_entries (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1: the entry amount is a double, and STO-4: no currency column.
    amount DOUBLE PRECISION NOT NULL,
    kind TEXT NOT NULL,
    -- TIM-1: created_at is a timestamp without time zone.
    created_at TIMESTAMP NOT NULL
);
