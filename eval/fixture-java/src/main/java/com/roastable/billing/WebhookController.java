package com.roastable.billing;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * The webhook endpoint a payment provider posts to. Runs the money side effect
 * straight from the delivered event. Mirrors the request handler behind
 * `@app.post("/webhooks")` in eval/fixture-py/webhooks.py.
 */
@RestController
public class WebhookController {

    private final WebhookService webhooks;

    public WebhookController(WebhookService webhooks) {
        this.webhooks = webhooks;
    }

    @PostMapping("/webhooks")
    public ResponseEntity<Void> handle(@RequestBody WebhookService.PaymentEvent event) {
        webhooks.handlePaymentSucceeded(event);
        return ResponseEntity.ok().build();
    }
}
