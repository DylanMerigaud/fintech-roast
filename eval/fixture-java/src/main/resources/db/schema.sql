-- Billing service schema. Mirrors eval/fixture-py/db/schema.sql.
-- This is the storage layer the JPA entities map onto and the service reads and
-- writes, so whatever the columns get wrong quietly spreads to every amount the
-- app moves.

CREATE TABLE accounts (
    id VARCHAR(64) PRIMARY KEY,
    owner_email VARCHAR(255) NOT NULL,
    balance NUMERIC(6, 2) NOT NULL DEFAULT 0
);

CREATE TABLE invoices (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL REFERENCES accounts (id),
    subtotal DOUBLE PRECISION NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    tax DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    issued_at TIMESTAMP NOT NULL
);

CREATE TABLE invoice_lines (
    id VARCHAR(64) PRIMARY KEY,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices (id),
    description VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);

CREATE TABLE payments (
    id VARCHAR(64) PRIMARY KEY,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices (id),
    amount DOUBLE PRECISION NOT NULL,
    external_ref VARCHAR(255),
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE webhook_events (
    id VARCHAR(64) PRIMARY KEY,
    event_id VARCHAR(255),
    event_type VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL REFERENCES accounts (id),
    amount DOUBLE PRECISION NOT NULL,
    received_at TIMESTAMP NOT NULL
);

CREATE TABLE ledger_entries (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL REFERENCES accounts (id),
    amount DOUBLE PRECISION NOT NULL,
    kind VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
