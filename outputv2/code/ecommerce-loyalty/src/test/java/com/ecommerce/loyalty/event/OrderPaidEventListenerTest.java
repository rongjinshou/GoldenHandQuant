package com.ecommerce.loyalty.event;

import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.loyalty.service.LoyaltyPointService;
import com.ecommerce.loyalty.service.MemberLevelService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link OrderPaidEventListener}.
 *
 * <p>The listener must react to {@code com.ecommerce.common.event.OrderPaidEvent}
 * — the class actually published by ecommerce-order — rather than a
 * module-local shadow. A previous version of this test constructed a
 * loyalty-local shadow event and called the listener method directly, which
 * "passed" even though Spring would never have dispatched a real,
 * order-published event to it (design spec §6.9 items 2 and 11).
 */
@ExtendWith(MockitoExtension.class)
class OrderPaidEventListenerTest {

    @Mock
    private LoyaltyPointService loyaltyPointService;

    @Mock
    private MemberLevelService memberLevelService;

    private OrderPaidEventListener listener;

    @BeforeEach
    void setUp() {
        listener = new OrderPaidEventListener(loyaltyPointService, memberLevelService);
    }

    private OrderPaidEvent commonEvent(Long orderId, Long userId, BigDecimal paidAmount) {
        return new OrderPaidEvent(new Object(), orderId, userId, paidAmount,
                List.of(new OrderPaidEvent.OrderItemPayload(10L, 2, new BigDecimal("75.00"))),
                "order-" + orderId, "trace-" + orderId);
    }

    /**
     * Verifies that when the COMMON OrderPaidEvent is published, the listener
     * calculates points via {@link LoyaltyPointService#calcOrderPoints} and
     * awards them via {@link LoyaltyPointService#earnPoints}.
     */
    @Test
    void testEarnPointsOnOrderPaid() {
        Long orderId = 100L;
        Long userId = 200L;
        BigDecimal paidAmount = new BigDecimal("150.00");

        OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);

        when(loyaltyPointService.calcOrderPoints(paidAmount, userId, 1.0))
                .thenReturn(16500);

        listener.onOrderPaid(event);

        verify(loyaltyPointService).calcOrderPoints(
                eq(paidAmount), eq(userId), eq(1.0));

        verify(loyaltyPointService).earnPoints(
                eq(userId), eq(16500), eq("ORDER"),
                eq(orderId.toString()),
                eq("Order payment reward, orderId=" + orderId));
    }

    /**
     * Verifies that when calcOrderPoints returns 0, earnPoints is NOT called.
     */
    @Test
    void testZeroPoints_doesNotEarnPoints() {
        OrderPaidEvent event = commonEvent(300L, 400L, BigDecimal.ZERO);

        when(loyaltyPointService.calcOrderPoints(BigDecimal.ZERO, 400L, 1.0))
                .thenReturn(0);

        listener.onOrderPaid(event);

        verify(loyaltyPointService, never()).earnPoints(any(), anyInt(), anyString(), anyString(), anyString());
    }

    /**
     * design spec §6.9 item 11: member level must be refreshed against the
     * user's up-to-date annual consumption BEFORE points are scored for this
     * same payment, so a tier crossed by this payment already applies to it.
     */
    @Test
    void testMemberLevelRefreshedBeforeScoring() {
        Long orderId = 500L;
        Long userId = 600L;
        BigDecimal paidAmount = new BigDecimal("6000.00");

        OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);
        when(loyaltyPointService.calcOrderPoints(paidAmount, userId, 1.0)).thenReturn(100);

        listener.onOrderPaid(event);

        verify(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);

        // The level refresh must happen before points are calculated so the
        // freshly-evaluated level's multiplier applies to this payment.
        InOrder order = inOrder(memberLevelService, loyaltyPointService);
        order.verify(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);
        order.verify(loyaltyPointService).calcOrderPoints(paidAmount, userId, 1.0);
    }

    /**
     * A failure in the member-level refresh must not propagate and roll back
     * the triggering payment transaction — the listener must swallow it just
     * like a failure in point-awarding (CLAUDE.md: post-payment side effects
     * must never block or roll back the main flow).
     */
    @Test
    void testMemberLevelRefreshFailure_doesNotPropagate() {
        Long orderId = 700L;
        Long userId = 800L;
        BigDecimal paidAmount = new BigDecimal("10.00");

        OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);
        org.mockito.Mockito.doThrow(new RuntimeException("boom"))
                .when(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);

        org.junit.jupiter.api.Assertions.assertDoesNotThrow(() -> listener.onOrderPaid(event));
    }
}
