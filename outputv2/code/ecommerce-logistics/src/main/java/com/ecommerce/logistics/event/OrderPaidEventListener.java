package com.ecommerce.logistics.event;

import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.logistics.repository.ShipmentRepository;
import com.ecommerce.logistics.service.ShipmentService;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.query.OrderQueryService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * Listens for {@link OrderPaidEvent} and auto-creates a shipment for the paid order
 * (design-docs/11 section 1: "订单支付成功后，物流服务通过监听 OrderPaidEvent 创建发货单，
 * 不应由订单服务同步调用" — logistics creates the shipment by listening to the event,
 * not via a synchronous call from the order module).
 *
 * <p>Runs after the triggering transaction commits, so a failure here can never roll
 * back the payment/order-paid transaction (design-docs/02 section 5: non-critical
 * listeners must not affect the transaction that published the event) — this is
 * exercised by PUB-108 via the {@code logistics-create-shipment-failure} fault
 * injection flag, which is why any failure is caught and logged here rather than
 * left to propagate.
 *
 * <p>The freight amount and delivery address are not carried on the event payload
 * (design-docs/附录D specifies {@code {orderId, userId, paidAmount, items}} only) —
 * per design-docs/11 section 4 ("运费最终以订单创建时计算结果为准"), the freight already
 * locked in at order-creation time is reused here via {@link OrderQueryService},
 * rather than recomputed.
 *
 * <p>Bean name is qualified with the module ({@code logisticsOrderPaidEventListener})
 * because ecommerce-loyalty also registers a component simple-named
 * {@code OrderPaidEventListener}; both are distinct, per-module reactions to the
 * same event and must both be registered, so an explicit name avoids the
 * {@code ConflictingBeanDefinitionException} that a shared default name would cause.
 */
@Component("logisticsOrderPaidEventListener")
public class OrderPaidEventListener {

    private static final Logger log = LoggerFactory.getLogger(OrderPaidEventListener.class);

    private final ShipmentService shipmentService;
    private final OrderQueryService orderQueryService;
    private final ShipmentRepository shipmentRepository;

    // Reports swallowed listener failures to the local event-failure table
    // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
    // unit tests keep working without this collaborator; Spring wires it in production.
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private com.ecommerce.common.event.DomainEventPublisher failureRecorder;

    public OrderPaidEventListener(ShipmentService shipmentService,
                                  OrderQueryService orderQueryService,
                                  ShipmentRepository shipmentRepository) {
        this.shipmentService = shipmentService;
        this.orderQueryService = orderQueryService;
        this.shipmentRepository = shipmentRepository;
    }

    // REQUIRES_NEW is essential: this listener fires AFTER_COMMIT of the order-paid
    // transaction, so no live transaction remains bound for writes. Without a fresh
    // transaction, ShipmentService.createShipment's save() would join the already
    // committed transaction and never flush — the shipment would appear "created"
    // (with a null id) but never actually persist, leaving the order with no shipment
    // to pick/ship/deliver. A new transaction here also keeps a shipment-creation
    // failure (e.g. the logistics-create-shipment-failure fault) from affecting the
    // payment transaction, which has already committed.
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderPaid(OrderPaidEvent event) {
        Long orderId = event.getOrderId();
        try {
            if (shipmentRepository.findByOrderId(orderId).isPresent()) {
                log.info("Shipment already exists for orderId={}, skipping auto-create", orderId);
                return;
            }

            OrderDto order = orderQueryService.getOrder(orderId);
            shipmentService.createShipment(orderId, event.getUserId(),
                    order.getShippingFee(), order.getAddressSnapshot());

            log.info("Auto-created shipment for orderId={} on OrderPaidEvent", orderId);
        } catch (Exception e) {
            log.error("Failed to auto-create shipment for orderId={}: {}", orderId, e.getMessage(), e);
            if (failureRecorder != null) {
                failureRecorder.recordListenerFailure(event, "logistics.OrderPaidEventListener", e);
            }
        }
    }
}
