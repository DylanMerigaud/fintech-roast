package com.roastable.billing;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * A recorded webhook delivery, mapping onto the webhook_events table
 * (db/schema.sql). Stands in for a processed-events table. Mirrors the event
 * dict in eval/fixture-py/webhooks.py.
 */
@Entity
@Table(name = "webhook_events")
public class WebhookEvent {

    @Id
    @Column(name = "id")
    private String id;

    @Column(name = "event_id")
    private String eventId;

    @Column(name = "event_type", nullable = false)
    private String eventType;

    @Column(name = "account_id", nullable = false)
    private String accountId;

    @Column(name = "amount", nullable = false)
    private double amount;

    @Column(name = "received_at", nullable = false)
    private LocalDateTime receivedAt;

    protected WebhookEvent() {
    }

    public WebhookEvent(String id, String eventId, String eventType, String accountId, double amount) {
        this.id = id;
        this.eventId = eventId;
        this.eventType = eventType;
        this.accountId = accountId;
        this.amount = amount;
        this.receivedAt = LocalDateTime.now();
    }

    public String getId() {
        return id;
    }

    public String getEventId() {
        return eventId;
    }

    public String getEventType() {
        return eventType;
    }

    public String getAccountId() {
        return accountId;
    }

    public double getAmount() {
        return amount;
    }
}
