package com.roastable.billing;

import org.springframework.data.jpa.repository.JpaRepository;

/** Spring Data access to the webhook_events table. */
public interface WebhookEventRepository extends JpaRepository<WebhookEvent, String> {
}
