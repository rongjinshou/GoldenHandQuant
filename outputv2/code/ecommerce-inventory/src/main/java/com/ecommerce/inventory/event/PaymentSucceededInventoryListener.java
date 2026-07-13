package com.ecommerce.inventory.event;

import com.ecommerce.common.event.PaymentSucceededEvent;
import com.ecommerce.inventory.query.InventoryReservationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * Deducts reserved stock once payment succeeds.
 *
 * <p>Order creation only <em>reserves</em> stock; the actual on-hand deduction
 * happens after payment (design-docs/01 §3 "创建订单时只预占库存，不扣减库存。支付成功后扣减库存"、
 * design-docs/06 §3 支付成功后扣减库存). design-docs/附录D §3 lists inventory-service as a
 * {@link PaymentSucceededEvent} listener; previously nothing consumed that event, so
 * paid orders never converted their reservation into a real deduction + outbound order.
 *
 * <p>{@code deductAfterPayment} is idempotent — it only processes still-RESERVED
 * reservations and marks them DEDUCTED — so a retried/duplicated payment callback
 * cannot double-deduct.
 *
 * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction: a deduction failure
 * must not roll back the payment (design-docs/02 §5), and the write needs a live
 * transaction to persist.
 */
@Component
public class PaymentSucceededInventoryListener {

    private static final Logger log = LoggerFactory.getLogger(PaymentSucceededInventoryListener.class);

    private final InventoryReservationService inventoryReservationService;

    // Reports swallowed listener failures to the local event-failure table
    // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
    // unit tests keep working without this collaborator; Spring wires it in production.
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private com.ecommerce.common.event.DomainEventPublisher failureRecorder;

    public PaymentSucceededInventoryListener(InventoryReservationService inventoryReservationService) {
        this.inventoryReservationService = inventoryReservationService;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onPaymentSucceeded(PaymentSucceededEvent event) {
        Long orderId = event.getOrderId();
        try {
            inventoryReservationService.deductAfterPayment(orderId);
            log.info("Deducted reserved stock for orderId={} on PaymentSucceededEvent", orderId);
        } catch (Exception e) {
            log.error("Failed to deduct stock for orderId={}: {}", orderId, e.getMessage(), e);
            if (failureRecorder != null) {
                failureRecorder.recordListenerFailure(event, "PaymentSucceededInventoryListener", e);
            }
        }
    }
}
