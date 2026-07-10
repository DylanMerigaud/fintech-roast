package com.roastable.billing;

import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Payment webhook handling for the billing service.
 *
 * <p>The money side effects a payment provider drives: a succeeded-payment
 * webhook that credits the customer, and an outbound charge call with a retry.
 * Mirrors eval/fixture-py/webhooks.py.
 */
@Service
public class WebhookService {

    /** The payment event a provider delivers. */
    public record PaymentEvent(String id, String type, String accountId, double amount) {
    }

    private final WebhookEventRepository events;
    private final Store store;
    private final HttpClient http = HttpClient.newHttpClient();

    public WebhookService(WebhookEventRepository events, Store store) {
        this.events = events;
        this.store = store;
    }

    /** Handle a payment.succeeded webhook by crediting the account. */
    @Transactional
    public void handlePaymentSucceeded(PaymentEvent event) {
        store.creditAccount(event.accountId(), BigDecimal.valueOf(event.amount()));
        events.save(new WebhookEvent(
                UUID.randomUUID().toString(), event.id(), event.type(), event.accountId(), event.amount()));
    }

    /** Charge a customer through the payment provider, retrying on failure. */
    public String chargeCustomer(String accountId, long amountCents, int attempts) {
        String body = "{\"account\":\"" + accountId + "\",\"amount\":" + amountCents + "}";
        RuntimeException lastError = null;
        for (int attempt = 0; attempt < attempts; attempt++) {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.payprovider.example/v1/charges"))
                    .header("content-type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            try {
                return http.send(request, HttpResponse.BodyHandlers.ofString()).body();
            } catch (Exception error) {
                lastError = new RuntimeException(error);
            }
        }
        throw new RuntimeException("charge failed after retries", lastError);
    }
}
