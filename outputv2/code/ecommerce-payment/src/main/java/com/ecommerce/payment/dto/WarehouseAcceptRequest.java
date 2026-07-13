package com.ecommerce.payment.dto;

/**
 * Request body for POST /api/v1/admin/refunds/{refundId}/warehouse-accept.
 *
 * <p>Mirrors the black-box harness payload ({@code RefundFixture#warehouseAccept}
 * sends {@code {"accepted": true|false}}): {@code true} means the returned goods
 * passed warehouse inspection, {@code false} means they failed it. The body is
 * optional — a missing body (or missing flag) keeps the historical behavior of
 * treating the call as an acceptance.
 */
public class WarehouseAcceptRequest {

    private Boolean accepted;

    public WarehouseAcceptRequest() {
    }

    public WarehouseAcceptRequest(Boolean accepted) {
        this.accepted = accepted;
    }

    public Boolean getAccepted() { return accepted; }
    public void setAccepted(Boolean accepted) { this.accepted = accepted; }
}
