package com.ecommerce.order.listener;

import com.ecommerce.common.event.ShipmentDeliveredEvent;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.order.service.OrderService;
import com.ecommerce.order.service.OrderStateMachine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * Advances the order to DELIVERED when logistics publishes the shared
 * {@link ShipmentDeliveredEvent} (design-docs/附录D §4: order-service listens to
 * ShipmentDeliveredEvent). This is the authoritative signal that the parcel was
 * received, which {@code OrderQueryService.verifyPurchase} then relies on to allow
 * a product review (design-docs/08 §2 order lifecycle: ... SHIPPED → DELIVERED).
 *
 * <p>The logistics {@code OrderLogisticsStatusUpdater} port is a no-op in the
 * running system, so the intermediate PICKING/SHIPPED statuses are never applied
 * to the order — it is still PAID when the parcel arrives. Like
 * {@code OrderQueryServiceImpl.markAsPaid} chains CREATED→PAYING→PAID, this
 * validates the designed hops up to DELIVERED rather than bypassing the state
 * machine with an ad-hoc jump.
 *
 * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction: a failure here must
 * never roll back the logistics delivery (design-docs/02 §5 — non-critical
 * listeners must not affect the publishing transaction), and the status write
 * needs a live transaction to actually persist.
 */
@Component
public class ShipmentDeliveredEventListener {

    private static final Logger log = LoggerFactory.getLogger(ShipmentDeliveredEventListener.class);

    private final OrderRepository orderRepository;
    private final OrderStateMachine stateMachine;
    private final OrderService orderService;

    public ShipmentDeliveredEventListener(OrderRepository orderRepository,
                                          OrderStateMachine stateMachine,
                                          OrderService orderService) {
        this.orderRepository = orderRepository;
        this.stateMachine = stateMachine;
        this.orderService = orderService;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onShipmentDelivered(ShipmentDeliveredEvent event) {
        Long orderId = event.getOrderId();
        try {
            Order order = orderRepository.findById(orderId).orElse(null);
            if (order == null) {
                log.warn("ShipmentDeliveredEvent for unknown orderId={}, ignoring", orderId);
                return;
            }

            OrderStatus from = order.getStatus();
            if (from == OrderStatus.DELIVERED || from == OrderStatus.COMPLETED) {
                return; // idempotent — delivery already recorded
            }

            // Validate the designed path to DELIVERED. Because the logistics status
            // port is a no-op, the order is normally still PAID here, so chain the
            // hops (PAID→PICKING→SHIPPED→DELIVERED) the state machine defines.
            if (from == OrderStatus.PAID) {
                stateMachine.validateTransition(OrderStatus.PAID, OrderStatus.PICKING);
                stateMachine.validateTransition(OrderStatus.PICKING, OrderStatus.SHIPPED);
                stateMachine.validateTransition(OrderStatus.SHIPPED, OrderStatus.DELIVERED);
            } else {
                stateMachine.validateTransition(from, OrderStatus.DELIVERED);
            }

            order.setStatus(OrderStatus.DELIVERED);
            orderRepository.save(order);

            orderService.recordEvent(orderId, from, OrderStatus.DELIVERED,
                    "DELIVERED", "LOGISTICS_SYSTEM",
                    "Shipment delivered, shipmentId=" + event.getShipmentId());

            log.info("Order {} marked DELIVERED on ShipmentDeliveredEvent (from {})", orderId, from);
        } catch (Exception e) {
            log.error("Failed to mark order {} delivered: {}", orderId, e.getMessage(), e);
        }
    }
}
