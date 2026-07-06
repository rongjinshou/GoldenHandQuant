package com.ecommerce.logistics.event;

import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.logistics.entity.Shipment;
import com.ecommerce.logistics.repository.ShipmentRepository;
import com.ecommerce.logistics.service.ShipmentService;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.query.OrderQueryService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link OrderPaidEventListener}.
 *
 * <p>Proves that paying an order triggers real, auto-created shipment creation
 * via the event (design-docs/11 section 1), that a shipment is never duplicated
 * for the same order, and that a failure here never propagates back out (PUB-108:
 * post-payment logistics failure must not block payment success).
 */
@ExtendWith(MockitoExtension.class)
class OrderPaidEventListenerTest {

    @Mock
    private ShipmentService shipmentService;
    @Mock
    private OrderQueryService orderQueryService;
    @Mock
    private ShipmentRepository shipmentRepository;

    @InjectMocks
    private OrderPaidEventListener orderPaidEventListener;

    @Test
    void onOrderPaid_createsShipmentForOrder() {
        Long orderId = 100L;
        Long userId = 200L;

        OrderDto order = new OrderDto();
        order.setOrderId(orderId);
        order.setUserId(userId);
        order.setShippingFee(new BigDecimal("8.00"));
        order.setAddressSnapshot("{\"province\":\"Guangdong\"}");

        when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
        when(orderQueryService.getOrder(orderId)).thenReturn(order);

        OrderPaidEvent event = new OrderPaidEvent(this, orderId, userId, new BigDecimal("108.00"),
                Collections.emptyList(), String.valueOf(orderId), null);

        orderPaidEventListener.onOrderPaid(event);

        verify(shipmentService).createShipment(orderId, userId, new BigDecimal("8.00"),
                "{\"province\":\"Guangdong\"}");
    }

    @Test
    void onOrderPaid_shipmentAlreadyExists_skipsCreation() {
        Long orderId = 101L;
        when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.of(new Shipment()));

        OrderPaidEvent event = new OrderPaidEvent(this, orderId, 200L, BigDecimal.TEN,
                Collections.emptyList(), String.valueOf(orderId), null);

        orderPaidEventListener.onOrderPaid(event);

        verify(shipmentService, never()).createShipment(any(), any(), any(), any());
        verify(orderQueryService, never()).getOrder(any());
    }

    @Test
    void onOrderPaid_shipmentCreationFails_doesNotPropagate() {
        Long orderId = 102L;
        when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
        when(orderQueryService.getOrder(orderId)).thenThrow(new RuntimeException("boom"));

        OrderPaidEvent event = new OrderPaidEvent(this, orderId, 200L, BigDecimal.TEN,
                Collections.emptyList(), String.valueOf(orderId), null);

        // Per PUB-108, a failed post-payment action must never bubble back up
        // and threaten the transaction that published the event.
        assertDoesNotThrow(() -> orderPaidEventListener.onOrderPaid(event));
    }

    @Test
    void onOrderPaid_shipmentServiceThrows_doesNotPropagate() {
        Long orderId = 103L;
        Long userId = 200L;
        OrderDto order = new OrderDto();
        order.setOrderId(orderId);
        order.setUserId(userId);
        order.setShippingFee(BigDecimal.ZERO);
        order.setAddressSnapshot("{}");

        when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
        when(orderQueryService.getOrder(orderId)).thenReturn(order);
        when(shipmentService.createShipment(any(), any(), any(), any()))
                .thenThrow(new RuntimeException("Fault injected: logistics-create-shipment-failure"));

        OrderPaidEvent event = new OrderPaidEvent(this, orderId, userId, BigDecimal.TEN,
                Collections.emptyList(), String.valueOf(orderId), null);

        assertDoesNotThrow(() -> orderPaidEventListener.onOrderPaid(event));
    }
}
