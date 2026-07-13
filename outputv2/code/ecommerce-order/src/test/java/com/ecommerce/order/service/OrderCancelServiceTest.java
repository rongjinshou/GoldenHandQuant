package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.inventory.query.InventoryReservationService;
import com.ecommerce.loyalty.query.LoyaltyCommandService;
import com.ecommerce.order.dto.CancelOrderResponse;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.promotion.service.CouponService;
import com.ecommerce.promotion.service.SeckillService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link OrderCancelService}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("OrderCancelService")
class OrderCancelServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private InventoryReservationService inventoryReservationService;

    @Mock
    private OrderStateMachine stateMachine;

    @Mock
    private DomainEventPublisher eventPublisher;

    @Mock
    private OrderService orderService;

    @Mock
    private CouponService couponService;

    @Mock
    private SeckillService seckillService;

    @Mock
    private LoyaltyCommandService loyaltyCommandService;

    @InjectMocks
    private OrderCancelService orderCancelService;

    private Order createdOrder;
    private Order paidOrder;
    private Order shippedOrder;
    private Order deliveredOrder;

    @BeforeEach
    void setUp() {
        createdOrder = new Order();
        createdOrder.setId(1L);
        createdOrder.setOrderNo("SO202606070001");
        createdOrder.setUserId(100L);
        createdOrder.setStatus(OrderStatus.CREATED);
        createdOrder.setPayableAmount(new BigDecimal("100.00"));
        createdOrder.setPaidAmount(BigDecimal.ZERO);

        paidOrder = new Order();
        paidOrder.setId(2L);
        paidOrder.setOrderNo("SO202606070002");
        paidOrder.setUserId(100L);
        paidOrder.setStatus(OrderStatus.PAID);
        paidOrder.setPayableAmount(new BigDecimal("200.00"));
        paidOrder.setPaidAmount(new BigDecimal("200.00"));

        shippedOrder = new Order();
        shippedOrder.setId(3L);
        shippedOrder.setOrderNo("SO202606070003");
        shippedOrder.setUserId(100L);
        shippedOrder.setStatus(OrderStatus.SHIPPED);
        shippedOrder.setPayableAmount(new BigDecimal("150.00"));

        deliveredOrder = new Order();
        deliveredOrder.setId(4L);
        deliveredOrder.setOrderNo("SO202606070004");
        deliveredOrder.setUserId(100L);
        deliveredOrder.setStatus(OrderStatus.DELIVERED);
        deliveredOrder.setPayableAmount(new BigDecimal("180.00"));
    }

    // ======================== Cancel CREATED order ========================

    @Test
    @DisplayName("cancel CREATED order: cancels and releases inventory")
    void testCancel_createdOrder_cancelsAndReleasesInventory() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(createdOrder));
        // stateMachine.validateTransition() is mocked void, won't throw
        when(orderRepository.save(any(Order.class))).thenReturn(createdOrder);

        CancelOrderResponse response = orderCancelService.cancel(100L, 1L, "No longer needed");

        assertThat(response.getOrderId()).isEqualTo(1L);
        assertThat(response.getStatus()).isEqualTo(OrderStatus.CANCELLED.name());
        assertThat(response.getMessage()).contains("inventory released");

        assertThat(createdOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        assertThat(createdOrder.getCancelReason()).isEqualTo("No longer needed");

        verify(inventoryReservationService).release(1L);
        verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
        verify(orderService).recordEvent(eq(1L), eq(OrderStatus.CREATED), eq(OrderStatus.CANCELLED),
                eq("CANCEL"), eq("100"), anyString());
    }

    @Test
    @DisplayName("cancel CREATED order: gives back coupons and seckill allocation")
    void testCancel_createdOrder_releasesCouponsAndSeckill() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(createdOrder));
        when(orderRepository.save(any(Order.class))).thenReturn(createdOrder);

        orderCancelService.cancel(100L, 1L, "No longer needed");

        verify(couponService).releaseForOrder(1L);
        verify(seckillService).releaseForOrder(1L);
        verify(loyaltyCommandService).refundPointsForOrder(1L);
    }

    @Test
    @DisplayName("cancel CREATED order: a release failure is swallowed and never blocks the cancellation")
    void testCancel_createdOrder_releaseFailureDoesNotBlockCancel() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(createdOrder));
        when(orderRepository.save(any(Order.class))).thenReturn(createdOrder);
        doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L);

        CancelOrderResponse response = orderCancelService.cancel(100L, 1L, "No longer needed");

        assertThat(response.getStatus()).isEqualTo(OrderStatus.CANCELLED.name());
        // The seckill half and the points refund still run even though the
        // coupon half failed.
        verify(seckillService).releaseForOrder(1L);
        verify(loyaltyCommandService).refundPointsForOrder(1L);
    }

    // ======================== Cancel PAYING order ========================

    @Test
    @DisplayName("cancel PAYING order: gives back coupons and seckill allocation")
    void testCancel_payingOrder_releasesCouponsAndSeckill() {
        Order payingOrder = new Order();
        payingOrder.setId(5L);
        payingOrder.setOrderNo("SO202606070005");
        payingOrder.setUserId(100L);
        payingOrder.setStatus(OrderStatus.PAYING);
        payingOrder.setPayableAmount(new BigDecimal("120.00"));
        payingOrder.setPaidAmount(BigDecimal.ZERO);
        when(orderRepository.findById(5L)).thenReturn(Optional.of(payingOrder));
        when(orderRepository.save(any(Order.class))).thenReturn(payingOrder);

        CancelOrderResponse response = orderCancelService.cancel(100L, 5L, "Changed my mind");

        assertThat(response.getStatus()).isEqualTo(OrderStatus.CANCELLED.name());
        verify(couponService).releaseForOrder(5L);
        verify(seckillService).releaseForOrder(5L);
        verify(loyaltyCommandService).refundPointsForOrder(5L);
    }

    // ======================== Cancel PAID order ========================

    @Test
    @DisplayName("cancel PAID order: moves to CANCEL_REVIEWING for merchant review, not cancelled directly")
    void testCancel_paidOrder_movesToCancelReviewing() {
        // A paid order must never jump straight to CANCELLED — it enters
        // merchant cancel review first (design-docs/08 §6).
        when(orderRepository.findById(2L)).thenReturn(Optional.of(paidOrder));
        // stateMachine.validateTransition() is mocked void, won't throw
        when(orderRepository.save(any(Order.class))).thenReturn(paidOrder);

        CancelOrderResponse response = orderCancelService.cancel(100L, 2L, "Changed my mind");

        assertThat(response.getOrderId()).isEqualTo(2L);
        assertThat(response.getStatus()).isEqualTo(OrderStatus.CANCEL_REVIEWING.name());
        assertThat(response.getMessage()).contains("review");
        assertThat(paidOrder.getStatus()).isEqualTo(OrderStatus.CANCEL_REVIEWING);

        // Inventory is not released at request time — only once the review is
        // approved (see reviewCancel), and no direct-refund fields are touched
        // here (order service does not compute or apply refunds itself).
        verify(inventoryReservationService, never()).release(anyLong());
        // Coupons/seckill allocation and the points deduction are likewise
        // kept until the review is approved.
        verify(couponService, never()).releaseForOrder(anyLong());
        verify(seckillService, never()).releaseForOrder(anyLong());
        verify(loyaltyCommandService, never()).refundPointsForOrder(anyLong());
    }

    @Test
    @DisplayName("cancel PAID order: paidAmount is left untouched pending merchant review")
    void testCancel_paidOrder_paidAmountUnchangedPendingReview() {
        when(orderRepository.findById(2L)).thenReturn(Optional.of(paidOrder));
        // stateMachine.validateTransition() is mocked void, won't throw
        when(orderRepository.save(any(Order.class))).thenReturn(paidOrder);

        orderCancelService.cancel(100L, 2L, "Refund please");

        // No refund is computed/applied by the order module at request time —
        // that belongs to payment's refund flow once the review is approved.
        assertThat(paidOrder.getPaidAmount()).isEqualTo(new BigDecimal("200.00"));
        assertThat(paidOrder.getStatus()).isEqualTo(OrderStatus.CANCEL_REVIEWING);
    }

    // ======================== Cancel SHIPPED order ========================

    @Test
    @DisplayName("cancel SHIPPED order throws BusinessException")
    void testCancel_shippedOrder_throwsException() {
        when(orderRepository.findById(3L)).thenReturn(Optional.of(shippedOrder));

        assertThatThrownBy(() -> orderCancelService.cancel(100L, 3L, "Cancel"))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("cannot be cancelled");
    }

    // ======================== Cancel DELIVERED order ========================

    @Test
    @DisplayName("cancel DELIVERED order throws BusinessException")
    void testCancel_deliveredOrder_throwsException() {
        when(orderRepository.findById(4L)).thenReturn(Optional.of(deliveredOrder));

        assertThatThrownBy(() -> orderCancelService.cancel(100L, 4L, "Cancel"))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("cannot be cancelled");
    }

    // ======================== Ownership verification ========================

    @Test
    @DisplayName("cancel order not owned by user throws BusinessException")
    void testCancel_notOwned_throwsException() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(createdOrder));

        assertThatThrownBy(() -> orderCancelService.cancel(999L, 1L, "Cancel"))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("does not belong to user");
    }

    // ======================== Order not found ========================

    @Test
    @DisplayName("cancel non-existent order throws ResourceNotFoundException")
    void testCancel_orderNotFound_throwsException() {
        when(orderRepository.findById(999L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> orderCancelService.cancel(100L, 999L, "Cancel"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Order not found");
    }

    // ======================== reviewCancel (admin) ========================

    @Test
    @DisplayName("reviewCancel approves cancellation: goes to CANCELLED")
    void testReviewCancel_approve() {
        Order reviewOrder = new Order();
        reviewOrder.setId(10L);
        reviewOrder.setStatus(OrderStatus.CANCEL_REVIEWING);

        when(orderRepository.findById(10L)).thenReturn(Optional.of(reviewOrder));
        // stateMachine.validateTransition() is mocked void, won't throw
        when(orderRepository.save(any(Order.class))).thenReturn(reviewOrder);

        CancelOrderResponse response = orderCancelService.reviewCancel(10L, true, "OK", 200L);

        assertThat(response.getStatus()).isEqualTo(OrderStatus.CANCELLED.name());
        assertThat(reviewOrder.getCancelReviewerId()).isEqualTo(200L);
        verify(inventoryReservationService).release(10L);
        verify(couponService).releaseForOrder(10L);
        verify(seckillService).releaseForOrder(10L);
        verify(loyaltyCommandService).refundPointsForOrder(10L);
    }

    @Test
    @DisplayName("reviewCancel rejects cancellation: goes back to PAID")
    void testReviewCancel_reject() {
        Order reviewOrder = new Order();
        reviewOrder.setId(11L);
        reviewOrder.setStatus(OrderStatus.CANCEL_REVIEWING);

        when(orderRepository.findById(11L)).thenReturn(Optional.of(reviewOrder));
        // stateMachine.validateTransition() is mocked void, won't throw
        when(orderRepository.save(any(Order.class))).thenReturn(reviewOrder);

        CancelOrderResponse response = orderCancelService.reviewCancel(11L, false, "Denied", 200L);

        assertThat(response.getStatus()).isEqualTo(OrderStatus.PAID.name());
    }
}
