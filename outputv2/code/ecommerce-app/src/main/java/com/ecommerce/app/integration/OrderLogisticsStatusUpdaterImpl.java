package com.ecommerce.app.integration;

import com.ecommerce.logistics.query.OrderLogisticsStatusUpdater;
import com.ecommerce.order.service.OrderLogisticsStatusService;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Component;

/**
 * Production implementation of the logistics module's
 * {@link OrderLogisticsStatusUpdater} port (design-docs/11 §3: "物流状态变更后，
 * 必须通过 OrderLogisticsStatusUpdater 更新对应订单的物流状态"). Delegates to the
 * order module's {@link OrderLogisticsStatusService}, which maps the shipment
 * status onto the order lifecycle through the order state machine.
 *
 * <p><b>Why this lives in ecommerce-app:</b> the port interface is declared in
 * {@code com.ecommerce.logistics.query}, but the behaviour belongs to the order
 * module — and ecommerce-logistics already depends on ecommerce-order at the
 * Maven level, so an implementation inside ecommerce-order would require an
 * order→logistics dependency and create a module cycle (design-docs/02 §2 has
 * no order→logistics edge). The app module is the composition root that sees
 * both modules, so the adapter is wired here.
 *
 * <p><b>Why {@code @Primary}:</b> the frozen black-box harness
 * ({@code BlackboxHarnessConfig} in test-cases, which must not be modified)
 * registers an unqualified no-op {@code OrderLogisticsStatusUpdater}
 * {@code @Bean}. With this production bean present there are two candidates of
 * the type; {@code @Primary} makes this one deterministically win type-based
 * injection into {@code ShipmentService} (Spring core semantics), while the
 * harness bean stays registered but un-injected — no
 * {@code NoUniqueBeanDefinitionException}, no harness change. Removing
 * {@code @Primary}, or adding a second {@code @Primary} candidate of this
 * type, would break every black-box test with an ambiguous-bean failure.
 *
 * <p>Never throws: the delegate swallows and logs all failures, because the
 * logistics endpoints must not 500 on an order-status race (e.g. an order
 * already in CANCEL_REVIEWING when the warehouse picks).
 */
@Component
@Primary
public class OrderLogisticsStatusUpdaterImpl implements OrderLogisticsStatusUpdater {

    private final OrderLogisticsStatusService orderLogisticsStatusService;

    public OrderLogisticsStatusUpdaterImpl(OrderLogisticsStatusService orderLogisticsStatusService) {
        this.orderLogisticsStatusService = orderLogisticsStatusService;
    }

    @Override
    public void updateLogisticsStatus(Long orderId, String logisticsStatus) {
        orderLogisticsStatusService.applyShipmentStatus(orderId, logisticsStatus);
    }
}
