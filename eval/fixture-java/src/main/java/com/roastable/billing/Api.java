package com.roastable.billing;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * JSON API surface for the billing service.
 *
 * <p>The response builders a set of read endpoints would return. Mirrors
 * eval/fixture-py/api.py.
 */
public final class Api {

    private Api() {
    }

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** An invoice as the read endpoint sees it. */
    public record InvoiceRecord(String id, long totalCents, String currency) {
    }

    /** A parsed inbound payment request. */
    public record PaymentRequest(double amount) {
    }

    /** Serialize an invoice for the GET /invoices/:id endpoint. */
    public static String invoiceResponse(InvoiceRecord invoice) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", invoice.id());
        payload.put("total", Money.fromMinorUnits(invoice.totalCents()));
        return write(payload);
    }

    /** Serialize an account balance for the GET /accounts/:id/balance endpoint. */
    public static String accountBalanceResponse(long balanceCents) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("balance", balanceCents);
        return write(payload);
    }

    /** Parse an inbound payment request body from the POST /payments endpoint. */
    public static PaymentRequest parsePaymentRequest(String body) {
        try {
            JsonNode parsed = MAPPER.readTree(body);
            return new PaymentRequest(Money.parseAmount(parsed.get("amount").asText()));
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("bad payment request", e);
        }
    }

    private static String write(Map<String, Object> payload) {
        try {
            return MAPPER.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }
}
