package com.ecommerce.order.service;

import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.repository.OrderRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link OrderLogisticsStatusService} — the order-module half of the
 * design-docs/11 §3 contract ("物流状态变更后，必须通过 OrderLogisticsStatusUpdater
 * 更新对应订单的物流状态").
 *
 * <p>Uses the real {@link OrderStateMachine} so the legal/illegal edges under
 * test are the production ones.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("OrderLogisticsStatusService")
class OrderLogisticsStatusServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private OrderService orderService;

    private OrderLogisticsStatusService service;

    @BeforeEach
    void setUp() {
        service = new OrderLogisticsStatusService(
                orderRepository, new OrderStateMachine(), orderService);
    }

    private Order order(Long id, OrderStatus status) {
        Order order = new Order();
        order.setId(id);
        order.setStatus(status);
        return order;
    }

    @Nested
    @DisplayName("legal progression")
    class LegalProgression {

        @Test
        @DisplayName("PICKING shipment status advances a PAID order to PICKING")
        void paidToPicking() {
            Order order = order(1L, OrderStatus.PAID);
            when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(1L, "PICKING");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.PICKING);
            verify(orderRepository).save(order);
            verify(orderService).recordEvent(eq(1L), eq(OrderStatus.PAID), eq(OrderStatus.PICKING),
                    eq("PICKING"), eq("LOGISTICS_SYSTEM"), any());
        }

        @Test
        @DisplayName("OUTBOUND shipment status advances a PICKING order to SHIPPED")
        void pickingToShipped() {
            Order order = order(2L, OrderStatus.PICKING);
            when(orderRepository.findById(2L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(2L, "OUTBOUND");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
            verify(orderRepository).save(order);
            verify(orderService).recordEvent(eq(2L), eq(OrderStatus.PICKING), eq(OrderStatus.SHIPPED),
                    eq("SHIPPED"), eq("LOGISTICS_SYSTEM"), any());
        }

        @Test
        @DisplayName("OUTBOUND from PAID chains the PAID→PICKING→SHIPPED hops")
        void paidToShippedChainsHops() {
            Order order = order(3L, OrderStatus.PAID);
            when(orderRepository.findById(3L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(3L, "OUTBOUND");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
            verify(orderRepository).save(order);
        }

        @Test
        @DisplayName("carrier COLLECTED / IN_TRANSIT map to SHIPPED")
        void carrierStatusesMapToShipped() {
            Order order = order(4L, OrderStatus.PICKING);
            when(orderRepository.findById(4L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(4L, "COLLECTED");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
        }
    }

    @Nested
    @DisplayName("illegal transition is skipped silently")
    class IllegalTransition {

        @Test
        @DisplayName("order in CANCEL_REVIEWING is not advanced and nothing is thrown")
        void cancelReviewingIsSkipped() {
            Order order = order(10L, OrderStatus.CANCEL_REVIEWING);
            when(orderRepository.findById(10L)).thenReturn(Optional.of(order));

            assertThatCode(() -> service.applyShipmentStatus(10L, "PICKING"))
                    .doesNotThrowAnyException();

            assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCEL_REVIEWING);
            verify(orderRepository, never()).save(any());
            verifyNoInteractions(orderService);
        }

        @Test
        @DisplayName("order in CANCELLED is not advanced")
        void cancelledIsSkipped() {
            Order order = order(11L, OrderStatus.CANCELLED);
            when(orderRepository.findById(11L)).thenReturn(Optional.of(order));

            assertThatCode(() -> service.applyShipmentStatus(11L, "OUTBOUND"))
                    .doesNotThrowAnyException();

            assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
            verify(orderRepository, never()).save(any());
        }

        @Test
        @DisplayName("unknown order is skipped without throwing")
        void unknownOrderIsSkipped() {
            when(orderRepository.findById(99L)).thenReturn(Optional.empty());

            assertThatCode(() -> service.applyShipmentStatus(99L, "PICKING"))
                    .doesNotThrowAnyException();

            verify(orderRepository, never()).save(any());
        }

        @Test
        @DisplayName("repository failure is swallowed, never propagated to logistics")
        void repositoryFailureIsSwallowed() {
            when(orderRepository.findById(anyLong()))
                    .thenThrow(new RuntimeException("db down"));

            assertThatCode(() -> service.applyShipmentStatus(12L, "PICKING"))
                    .doesNotThrowAnyException();
        }
    }

    @Nested
    @DisplayName("idempotency")
    class Idempotency {

        @Test
        @DisplayName("order already at the target status is a no-op")
        void alreadyAtTarget() {
            Order order = order(20L, OrderStatus.PICKING);
            when(orderRepository.findById(20L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(20L, "PICKING");

            verify(orderRepository, never()).save(any());
            verifyNoInteractions(orderService);
        }

        @Test
        @DisplayName("order already past the target status is a no-op (no regression)")
        void alreadyPastTarget() {
            Order order = order(21L, OrderStatus.SHIPPED);
            when(orderRepository.findById(21L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(21L, "PICKING");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
            verify(orderRepository, never()).save(any());
        }

        @Test
        @DisplayName("late carrier event after delivery is ignored")
        void deliveredOrderIgnoresLateEvents() {
            Order order = order(22L, OrderStatus.DELIVERED);
            when(orderRepository.findById(22L)).thenReturn(Optional.of(order));

            service.applyShipmentStatus(22L, "IN_TRANSIT");

            assertThat(order.getStatus()).isEqualTo(OrderStatus.DELIVERED);
            verify(orderRepository, never()).save(any());
        }
    }

    @Nested
    @DisplayName("statuses without order-side progression")
    class NoProgressionStatuses {

        @Test
        @DisplayName("LABEL_PRINTED does not touch the order")
        void labelPrintedIsNoOp() {
            service.applyShipmentStatus(30L, "LABEL_PRINTED");
            verifyNoInteractions(orderRepository, orderService);
        }

        @Test
        @DisplayName("DELIVERED is left to ShipmentDeliveredEventListener")
        void deliveredIsNoOpHere() {
            service.applyShipmentStatus(31L, "DELIVERED");
            verifyNoInteractions(orderRepository, orderService);
        }

        @Test
        @DisplayName("EXCEPTION and null do not touch the order")
        void exceptionAndNullAreNoOps() {
            service.applyShipmentStatus(32L, "EXCEPTION");
            service.applyShipmentStatus(32L, null);
            verifyNoInteractions(orderRepository, orderService);
        }
    }
}
