package com.ecommerce.order.service;

import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.repository.OrderRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Advances an order's fulfilment status when the logistics module reports a
 * shipment status change (design-docs/11 §3: "物流状态变更后，必须通过
 * OrderLogisticsStatusUpdater 更新对应订单的物流状态").
 *
 * <p>This service is the order-module half of that contract: it maps the
 * logistics-side {@code ShipmentStatus} string onto the order lifecycle
 * (design-docs/08 §2) and applies the transition through the
 * {@link OrderStateMachine}:
 *
 * <ul>
 *   <li>{@code PICKING} → order {@code PICKING} (拣货中)</li>
 *   <li>{@code OUTBOUND} / {@code COLLECTED} / {@code IN_TRANSIT} → order
 *       {@code SHIPPED} (已发货 — the parcel has left the warehouse)</li>
 *   <li>{@code CREATED} / {@code LABEL_PRINTED} / {@code EXCEPTION} — no
 *       order-side progression (label printing keeps the order 拣货中;
 *       a carrier exception does not move the order lifecycle)</li>
 *   <li>{@code DELIVERED} — intentionally NOT handled here. Delivery is
 *       propagated by the shared {@code ShipmentDeliveredEvent} and applied by
 *       {@code ShipmentDeliveredEventListener} (design-docs/附录D §4), which
 *       stays the single authoritative DELIVERED writer.</li>
 * </ul>
 *
 * <p><b>Tolerance semantics — this method never throws.</b> It is invoked
 * inside the logistics transaction (pick / print-label / outbound / carrier
 * callback); a missing order or a status race (e.g. the order moved to
 * CANCEL_REVIEWING or REFUNDING while the warehouse kept working) must not
 * 500 the logistics endpoint. Such cases are logged at WARN and skipped —
 * the same tolerance paradigm as {@code ShipmentDeliveredEventListener}.
 * Hops are checked with {@link OrderStateMachine#canTransition} (boolean),
 * never the throwing validator. An order already at or past the target
 * status is an idempotent no-op.
 *
 * <p>Runs in the caller's transaction (default REQUIRED) so the order-status
 * write commits atomically with the shipment-status write that triggered it.
 */
@Service
public class OrderLogisticsStatusService {

    private static final Logger log = LoggerFactory.getLogger(OrderLogisticsStatusService.class);

    /**
     * The forward fulfilment chain a paid order walks (design-docs/08 §2).
     * A logistics update may only advance the order along this chain; every
     * hop is still validated against the {@link OrderStateMachine}.
     */
    private static final List<OrderStatus> FULFILMENT_CHAIN =
            List.of(OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED);

    private final OrderRepository orderRepository;
    private final OrderStateMachine stateMachine;
    private final OrderService orderService;

    public OrderLogisticsStatusService(OrderRepository orderRepository,
                                       OrderStateMachine stateMachine,
                                       OrderService orderService) {
        this.orderRepository = orderRepository;
        this.stateMachine = stateMachine;
        this.orderService = orderService;
    }

    /**
     * Apply a logistics-side shipment status to the owning order.
     *
     * @param orderId        the order the shipment belongs to
     * @param shipmentStatus the logistics status name as reported by the
     *                       logistics module (a {@code ShipmentStatus} name)
     */
    @Transactional
    public void applyShipmentStatus(Long orderId, String shipmentStatus) {
        try {
            OrderStatus target = mapToOrderStatus(shipmentStatus);
            if (target == null) {
                log.debug("Logistics status {} has no order-side progression, orderId={}",
                        shipmentStatus, orderId);
                return;
            }
            if (orderId == null) {
                log.warn("Logistics status {} reported without an orderId, skipping", shipmentStatus);
                return;
            }

            Order order = orderRepository.findById(orderId).orElse(null);
            if (order == null) {
                log.warn("Logistics status {} for unknown orderId={}, skipping", shipmentStatus, orderId);
                return;
            }

            OrderStatus from = order.getStatus();
            if (from == target) {
                return; // idempotent — already at the target status
            }

            int fromIdx = FULFILMENT_CHAIN.indexOf(from);
            int targetIdx = FULFILMENT_CHAIN.indexOf(target);
            if (fromIdx < 0) {
                if (from == OrderStatus.DELIVERED || from == OrderStatus.COMPLETED
                        || from == OrderStatus.REFUNDING || from == OrderStatus.REFUNDED) {
                    // Late/replayed logistics event after delivery — idempotent no-op.
                    log.debug("Order {} already past fulfilment (status={}), ignoring logistics status {}",
                            orderId, from, shipmentStatus);
                } else {
                    // e.g. CANCEL_REVIEWING / CANCELLED / CLOSED race with the warehouse.
                    log.warn("Order {} in status {} is not eligible for logistics progression to {}, skipping",
                            orderId, from, target);
                }
                return;
            }
            if (fromIdx > targetIdx) {
                return; // idempotent — already past the target status
            }

            // Validate every hop of the chain (e.g. PAID→PICKING→SHIPPED) instead
            // of jumping — same paradigm as ShipmentDeliveredEventListener.
            for (int i = fromIdx; i < targetIdx; i++) {
                OrderStatus hopFrom = FULFILMENT_CHAIN.get(i);
                OrderStatus hopTo = FULFILMENT_CHAIN.get(i + 1);
                if (!stateMachine.canTransition(hopFrom, hopTo)) {
                    log.warn("Order {} cannot advance {} -> {} (hop {} -> {} not allowed), skipping",
                            orderId, from, target, hopFrom, hopTo);
                    return;
                }
            }

            order.setStatus(target);
            orderRepository.save(order);

            orderService.recordEvent(orderId, from, target, target.name(), "LOGISTICS_SYSTEM",
                    "Logistics status sync: " + shipmentStatus);

            log.info("Order {} advanced {} -> {} on logistics status {}",
                    orderId, from, target, shipmentStatus);
        } catch (Exception e) {
            // Never propagate: the logistics flow must not fail because the
            // order could not be advanced (design-docs/02 §5 tolerance).
            log.warn("Failed to apply logistics status {} to order {}: {}",
                    shipmentStatus, orderId, e.getMessage(), e);
        }
    }

    /**
     * Map a logistics {@code ShipmentStatus} name to the order status it
     * implies, or {@code null} when the order lifecycle is unaffected.
     */
    private OrderStatus mapToOrderStatus(String shipmentStatus) {
        if (shipmentStatus == null) {
            return null;
        }
        switch (shipmentStatus.toUpperCase()) {
            case "PICKING":
                return OrderStatus.PICKING;
            case "OUTBOUND":
            case "COLLECTED":
            case "IN_TRANSIT":
                return OrderStatus.SHIPPED;
            default:
                // CREATED, LABEL_PRINTED, DELIVERED (event-driven), EXCEPTION, unknown
                return null;
        }
    }
}
