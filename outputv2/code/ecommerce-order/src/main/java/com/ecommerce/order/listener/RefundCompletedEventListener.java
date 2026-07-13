package com.ecommerce.order.listener;

import com.ecommerce.common.event.RefundCompletedEvent;
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
 * Advances the order to REFUNDED when payment publishes the shared
 * {@link RefundCompletedEvent} (design-docs/02 §5: order listens to
 * RefundCompletedEvent to "更新售后状态"). {@code RefundService.applyRefund}
 * does not itself touch order status (a refund can be applied any time after
 * a successful payment), so this listener is the only writer of REFUNDING and
 * REFUNDED — both only defined from DELIVERED in {@link OrderStateMachine}.
 *
 * <p>An order that is refunded before reaching DELIVERED (still PAID/PICKING/
 * SHIPPED) has no defined path to REFUNDED in the state machine; this listener
 * only performs the transition the design defines and logs+skips otherwise,
 * rather than inventing an undocumented one.
 *
 * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction, matching every
 * other non-critical cross-module listener in this system (design-docs/02 §5):
 * a failure here must never roll back the refund completion itself.
 */
@Component
public class RefundCompletedEventListener {

    private static final Logger log = LoggerFactory.getLogger(RefundCompletedEventListener.class);

    private final OrderRepository orderRepository;
    private final OrderStateMachine stateMachine;
    private final OrderService orderService;

    // Reports swallowed listener failures to the local event-failure table
    // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
    // unit tests keep working without this collaborator; Spring wires it in production.
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private com.ecommerce.common.event.DomainEventPublisher failureRecorder;

    public RefundCompletedEventListener(OrderRepository orderRepository,
                                         OrderStateMachine stateMachine,
                                         OrderService orderService) {
        this.orderRepository = orderRepository;
        this.stateMachine = stateMachine;
        this.orderService = orderService;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onRefundCompleted(RefundCompletedEvent event) {
        Long orderId = event.getOrderId();
        try {
            Order order = orderRepository.findById(orderId).orElse(null);
            if (order == null) {
                log.warn("RefundCompletedEvent for unknown orderId={}, ignoring", orderId);
                return;
            }

            OrderStatus from = order.getStatus();
            if (from == OrderStatus.REFUNDED || from == OrderStatus.COMPLETED) {
                return; // idempotent — refund already recorded
            }
            if (from != OrderStatus.DELIVERED && from != OrderStatus.REFUNDING) {
                log.warn("Order {} refunded while in status {} — no defined path to REFUNDED, skipping",
                        orderId, from);
                return;
            }

            if (from == OrderStatus.DELIVERED) {
                stateMachine.validateTransition(OrderStatus.DELIVERED, OrderStatus.REFUNDING);
            }
            stateMachine.validateTransition(OrderStatus.REFUNDING, OrderStatus.REFUNDED);

            order.setStatus(OrderStatus.REFUNDED);
            orderRepository.save(order);

            orderService.recordEvent(orderId, from, OrderStatus.REFUNDED,
                    "REFUNDED", "PAYMENT_SYSTEM",
                    "Refund completed, refundNo=" + event.getRefundNo());

            log.info("Order {} marked REFUNDED on RefundCompletedEvent (from {})", orderId, from);
        } catch (Exception e) {
            log.error("Failed to mark order {} refunded: {}", orderId, e.getMessage(), e);
            if (failureRecorder != null) {
                failureRecorder.recordListenerFailure(event, "order.RefundCompletedEventListener", e);
            }
        }
    }
}
