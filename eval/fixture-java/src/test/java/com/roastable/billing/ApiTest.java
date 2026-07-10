package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

/**
 * Green-by-design api tests.
 *
 * <p>Round-number totals and balances (10000 cents, 9000 cents, 250.00), so the
 * float round-trip and the inconsistent unit across endpoints stay dormant.
 */
class ApiTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void invoiceResponseSerializesTotal() throws Exception {
        JsonNode payload = mapper.readTree(
                Api.invoiceResponse(new Api.InvoiceRecord("inv_1", 10000, "USD")));
        assertEquals(100.0, payload.get("total").asDouble());
    }

    @Test
    void accountBalanceResponseReturnsCents() throws Exception {
        JsonNode payload = mapper.readTree(Api.accountBalanceResponse(9000));
        assertEquals(9000, payload.get("balance").asLong());
    }

    @Test
    void parsePaymentRequest() {
        assertEquals(250.0, Api.parsePaymentRequest("{\"amount\":\"250.00\"}").amount());
    }
}
