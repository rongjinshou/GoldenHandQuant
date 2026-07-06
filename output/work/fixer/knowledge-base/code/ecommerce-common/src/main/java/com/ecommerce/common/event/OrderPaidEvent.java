package com.ecommerce.common.event;

import java.math.BigDecimal;
import java.util.List;

/**
 * Published by ecommerce-order when an order transitions to PAID.
 * Listened to by ecommerce-logistics, ecommerce-loyalty, and common notification
 * (design-docs/附录D section 2). Lives in common because loyalty (which only
 * depends on ecommerce-common) must be able to listen to it via
 * {@code @EventListener} without a cross-module dependency on ecommerce-order.
 */
public class OrderPaidEvent extends AbstractDomainEvent {

    private final Long orderId;
    private final Long userId;
    private final BigDecimal paidAmount;
    private final List<OrderItemPayload> items;

    public OrderPaidEvent(Object source, Long orderId, Long userId, BigDecimal paidAmount,
                           List<OrderItemPayload> items, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.orderId = orderId;
        this.userId = userId;
        this.paidAmount = paidAmount;
        this.items = items;
    }

    public Long getOrderId() { return orderId; }
    public Long getUserId() { return userId; }
    public BigDecimal getPaidAmount() { return paidAmount; }
    public List<OrderItemPayload> getItems() { return items; }

    public static class OrderItemPayload {
        private final Long skuId;
        private final Integer quantity;
        private final BigDecimal price;

        public OrderItemPayload(Long skuId, Integer quantity, BigDecimal price) {
            this.skuId = skuId;
            this.quantity = quantity;
            this.price = price;
        }

        public Long getSkuId() { return skuId; }
        public Integer getQuantity() { return quantity; }
        public BigDecimal getPrice() { return price; }
    }
}
