-- Billing service schema (Postgres). Correct twin of fixture-py/db/schema.sql.
-- Every money column is exact DECIMAL with a currency alongside, instants are
-- stored with a time zone, and the provider references that must not duplicate
-- carry UNIQUE constraints. Nothing here should trip the storage or identity
-- rules; that is the point of the clean fixture.

CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    -- STO-2 corrected: a running balance with plenty of headroom (NUMERIC(20,4)),
    -- exact decimal, no overflow at realistic magnitudes.
    balance NUMERIC(20,4) NOT NULL DEFAULT 0,
    -- STO-4 corrected: every stored amount has a currency next to it.
    currency CHAR(3) NOT NULL
);

CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1 corrected: money stored as exact decimal, not binary float.
    subtotal NUMERIC(20,4) NOT NULL,
    discount_pct NUMERIC(6,4) NOT NULL DEFAULT 0,
    tax NUMERIC(20,4) NOT NULL,
    total NUMERIC(20,4) NOT NULL,
    -- STO-4 corrected: the invoice's currency travels with its amounts.
    currency CHAR(3) NOT NULL,
    -- TIM-1 corrected: a financial instant stored with a time zone.
    issued_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE invoice_lines (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    -- STO-1 corrected: a unit price stored as exact decimal.
    unit_price NUMERIC(20,4) NOT NULL
);

CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    -- STO-1 corrected: payment amount stored as exact decimal.
    amount NUMERIC(20,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    -- IDE-4 corrected: the provider reference is UNIQUE, so a redelivered
    -- provider event cannot insert a second payment row for the same ref.
    external_ref TEXT UNIQUE,
    -- TIM-1 corrected: received_at is a timestamp WITH time zone.
    received_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE webhook_events (
    id TEXT PRIMARY KEY,
    -- IDE-4 corrected: the provider event id is UNIQUE, so the same event
    -- recorded twice is rejected by the database, backing up the app dedup.
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1 / STO-4 corrected: exact decimal amount with a currency.
    amount NUMERIC(20,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    -- TIM-1 corrected: received_at is a timestamp WITH time zone.
    received_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE ledger_entries (
    id TEXT PRIMARY KEY,
    -- LED-2 corrected: entries are grouped by a shared transaction id, so the
    -- two legs of one movement can be found and balanced together.
    transaction_id TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    -- STO-1 / STO-4 corrected: exact decimal amount with a currency.
    amount NUMERIC(20,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('debit', 'credit')),
    -- LED-4 corrected: every entry carries who moved the money and why.
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    -- TIM-1 corrected: created_at is a timestamp WITH time zone.
    created_at TIMESTAMPTZ NOT NULL
);
