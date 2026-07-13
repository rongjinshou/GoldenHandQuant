package com.ecommerce.common.event;

import java.time.LocalDateTime;

/**
 * Published by ecommerce-logistics when a shipment is marked delivered.
 * Listened to by ecommerce-order and ecommerce-loyalty (design-docs/附录D
 * section 4). Lives in common because neither order nor loyalty depends on
 * ecommerce-logistics, so neither could otherwise reference the publisher's
 * event class from an {@code @EventListener}.
 */
public class ShipmentDeliveredEvent extends AbstractDomainEvent {

    private final Long orderId;
    private final Long shipmentId;
    private final LocalDateTime deliveredAt;

    public ShipmentDeliveredEvent(Object source, Long orderId, Long shipmentId,
                                   LocalDateTime deliveredAt, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.orderId = orderId;
        this.shipmentId = shipmentId;
        this.deliveredAt = deliveredAt;
    }

    public Long getOrderId() { return orderId; }
    public Long getShipmentId() { return shipmentId; }
    public LocalDateTime getDeliveredAt() { return deliveredAt; }
}
