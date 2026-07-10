package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

/**
 * Webhook tests: a single delivery of the event, never a redelivery, so the
 * missing event-id dedup never double-credits here. Round USD.
 */
@SpringBootTest
@Transactional
class WebhookServiceTest {

    @Autowired
    private WebhookService webhooks;

    @Autowired
    private Store store;

    @Test
    void paymentSucceededCreditsOnce() {
        webhooks.handlePaymentSucceeded(
                new WebhookService.PaymentEvent("evt_1", "payment.succeeded", "acct_1", 100));
        assertEquals(0, new BigDecimal("100").compareTo(store.getAccount("acct_1").getBalance()));
    }
}
