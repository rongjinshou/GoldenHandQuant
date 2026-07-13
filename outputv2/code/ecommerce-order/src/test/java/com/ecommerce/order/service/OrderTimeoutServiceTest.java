package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.inventory.query.InventoryReservationService;
import com.ecommerce.loyalty.query.LoyaltyCommandService;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.promotion.service.CouponService;
import com.ecommerce.promotion.service.SeckillService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link OrderTimeoutService}.
 *
 * <p>When this service finds and cancels an expired order, it also releases
 * the pre-occupied inventory via {@code InventoryReservationService.release()}
 * so the reserved stock does not remain occupied indefinitely.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("OrderTimeoutService")
class OrderTimeoutServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private DomainEventPublisher eventPublisher;

    @Mock
    private OrderService orderService;

    @Mock
    private InventoryReservationService inventoryReservationService;

    @Mock
    private CouponService couponService;

    @Mock
    private SeckillService seckillService;

    @Mock
    private LoyaltyCommandService loyaltyCommandService;

    @InjectMocks
    private OrderTimeoutService orderTimeoutService;

    private Order expiredOrder;

    @BeforeEach
    void setUp() {
        expiredOrder = new Order();
        expiredOrder.setId(1L);
        expiredOrder.setOrderNo("SO202606070001");
        expiredOrder.setUserId(100L);
        expiredOrder.setStatus(OrderStatus.CREATED);
        expiredOrder.setPayableAmount(new BigDecimal("150.00"));
        expiredOrder.setExpiresAt(LocalDateTime.now().minusHours(1));
        // setCreatedAt to mock BaseEntity field — required for event recording
    }

    // ======================== timeout cancellation ========================

    @Test
    @DisplayName("timeout cancels expired order")
    void testTimeout_cancelsExpiredOrder() {
        when(orderRepository.findByStatusAndExpiresAtBefore(eq(OrderStatus.CREATED), any(LocalDateTime.class)))
                .thenReturn(List.of(expiredOrder));

        orderTimeoutService.cancelExpiredOrders();

        // Verify the order is marked as CANCELLED
        assertThat(expiredOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        assertThat(expiredOrder.getCancelReason()).contains("expired");

        // Verify cancel reason contains "60 minutes"
        assertThat(expiredOrder.getCancelReason()).contains("60 minutes");
    }

    @Test
    @DisplayName("timeout releases the reserved inventory for the expired order")
    void testCancelExpiredOrder_releasesReservedInventory() {
        orderTimeoutService.cancelExpiredOrder(expiredOrder);

        verify(inventoryReservationService).release(expiredOrder.getId());
    }

    @Test
    @DisplayName("timeout gives back coupons, seckill allocation and redeemed points")
    void testCancelExpiredOrder_releasesPromotionsAndRefundsPoints() {
        orderTimeoutService.cancelExpiredOrder(expiredOrder);

        verify(couponService).releaseForOrder(1L);
        verify(seckillService).releaseForOrder(1L);
        verify(loyaltyCommandService).refundPointsForOrder(1L);
    }

    @Test
    @DisplayName("timeout release/refund failures are swallowed and never block the cancellation")
    void testCancelExpiredOrder_releaseFailureDoesNotBlockCancel() {
        doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L);
        doThrow(new RuntimeException("refund boom")).when(loyaltyCommandService).refundPointsForOrder(1L);

        orderTimeoutService.cancelExpiredOrder(expiredOrder);

        // The cancellation still completes: order flipped, seckill half still
        // released, event recorded and published despite both failures.
        assertThat(expiredOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        verify(seckillService).releaseForOrder(1L);
        verify(orderService).recordEvent(eq(1L), eq(OrderStatus.CREATED), eq(OrderStatus.CANCELLED),
                eq("TIMEOUT_CANCEL"), eq("SYSTEM"), anyString());
        verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
    }

    @Test
    @DisplayName("timeout cancels order and publishes OrderCancelledEvent")
    void testTimeout_publishesOrderCancelledEvent() {
        when(orderRepository.findByStatusAndExpiresAtBefore(eq(OrderStatus.CREATED), any(LocalDateTime.class)))
                .thenReturn(List.of(expiredOrder));

        orderTimeoutService.cancelExpiredOrders();

        verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
    }

    @Test
    @DisplayName("timeout records event log for cancelled order")
    void testTimeout_recordsEventLog() {
        when(orderRepository.findByStatusAndExpiresAtBefore(eq(OrderStatus.CREATED), any(LocalDateTime.class)))
                .thenReturn(List.of(expiredOrder));

        orderTimeoutService.cancelExpiredOrders();

        verify(orderService).recordEvent(
                eq(1L),
                eq(OrderStatus.CREATED),
                eq(OrderStatus.CANCELLED),
                eq("TIMEOUT_CANCEL"),
                eq("SYSTEM"),
                anyString());
    }

    @Test
    @DisplayName("timeout with no expired orders does nothing")
    void testTimeout_noExpiredOrders_doesNothing() {
        when(orderRepository.findByStatusAndExpiresAtBefore(eq(OrderStatus.CREATED), any(LocalDateTime.class)))
                .thenReturn(Collections.emptyList());

        orderTimeoutService.cancelExpiredOrders();

        verify(orderService, never()).recordEvent(any(), any(), any(), anyString(), anyString(), anyString());
        verify(eventPublisher, never()).publish(any());
    }
}
