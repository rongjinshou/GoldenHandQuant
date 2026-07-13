package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.order.dto.VerifyPurchaseResponse;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderItem;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.repository.OrderItemRepository;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.product.query.ProductQueryService;
import com.ecommerce.product.query.SkuDto;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link OrderQueryServiceImpl}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("OrderQueryServiceImpl")
class OrderQueryServiceImplTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private OrderItemRepository orderItemRepository;

    @Mock
    private ProductQueryService productQueryService;

    @Mock
    private DomainEventPublisher eventPublisher;

    // Real (not mocked) OrderStateMachine: it's a pure, dependency-free logic
    // component, so using the real instance gives genuine regression coverage
    // for markAsPaid's transition validation instead of just asserting a
    // mock was called.
    private final OrderStateMachine stateMachine = new OrderStateMachine();

    private OrderQueryServiceImpl orderQueryService;

    private Order order;
    private Order paidOrder;
    private Order deliveredOrder;

    @BeforeEach
    void setUp() {
        orderQueryService = new OrderQueryServiceImpl(
                orderRepository, orderItemRepository, productQueryService,
                stateMachine, eventPublisher);

        order = new Order();
        order.setId(1L);
        order.setOrderNo("SO202606070001");
        order.setUserId(100L);
        order.setStatus(OrderStatus.CREATED);
        order.setItemTotal(new BigDecimal("100.00"));
        order.setShippingFee(new BigDecimal("8.00"));
        order.setPackagingFee(new BigDecimal("2.00"));
        order.setDiscountAmount(new BigDecimal("5.00"));
        order.setPointsDeductionAmount(BigDecimal.ZERO);
        order.setPayableAmount(new BigDecimal("97.00"));
        order.setPaidAmount(BigDecimal.ZERO);
        order.setCreatedAt(LocalDateTime.now());
        order.setUpdatedAt(LocalDateTime.now());

        paidOrder = new Order();
        paidOrder.setId(2L);
        paidOrder.setOrderNo("SO202606070002");
        paidOrder.setUserId(100L);
        paidOrder.setStatus(OrderStatus.PAID);
        paidOrder.setPayableAmount(new BigDecimal("200.00"));
        paidOrder.setPaidAmount(new BigDecimal("200.00"));
        paidOrder.setCreatedAt(LocalDateTime.now());
        paidOrder.setUpdatedAt(LocalDateTime.now());

        deliveredOrder = new Order();
        deliveredOrder.setId(3L);
        deliveredOrder.setOrderNo("SO202606070003");
        deliveredOrder.setUserId(100L);
        deliveredOrder.setStatus(OrderStatus.DELIVERED);
        deliveredOrder.setPayableAmount(new BigDecimal("150.00"));
        deliveredOrder.setCreatedAt(LocalDateTime.now().minusDays(5));
        deliveredOrder.setUpdatedAt(LocalDateTime.now());
    }

    // ======================== getOrder ========================

    @Test
    @DisplayName("getOrder returns OrderDto for existing order")
    void testGetOrder_existing_returnsDto() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

        OrderDto result = orderQueryService.getOrder(1L);

        assertThat(result).isNotNull();
        assertThat(result.getOrderId()).isEqualTo(1L);
        assertThat(result.getOrderNo()).isEqualTo("SO202606070001");
        assertThat(result.getStatus()).isEqualTo(OrderStatus.CREATED);
        assertThat(result.getPayableAmount()).isEqualTo(new BigDecimal("97.00"));
    }

    @Test
    @DisplayName("getOrder throws ResourceNotFoundException for non-existing order")
    void testGetOrder_notFound_throwsException() {
        when(orderRepository.findById(999L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> orderQueryService.getOrder(999L))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Order not found");
    }

    // ======================== getPayableOrder ========================

    @Test
    @DisplayName("getPayableOrder returns OrderDto for CREATED order")
    void testGetPayableOrder_created_returnsDto() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

        OrderDto result = orderQueryService.getPayableOrder(1L);

        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo(OrderStatus.CREATED);
    }

    @Test
    @DisplayName("getPayableOrder throws for non-payable status (PAID)")
    void testGetPayableOrder_paid_throwsException() {
        when(orderRepository.findById(2L)).thenReturn(Optional.of(paidOrder));

        assertThatThrownBy(() -> orderQueryService.getPayableOrder(2L))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("cannot be paid");
    }

    @Test
    @DisplayName("getPayableOrder throws for CANCELLED order")
    void testGetPayableOrder_cancelled_throwsException() {
        Order cancelledOrder = new Order();
        cancelledOrder.setId(5L);
        cancelledOrder.setStatus(OrderStatus.CANCELLED);
        cancelledOrder.setCreatedAt(LocalDateTime.now());
        when(orderRepository.findById(5L)).thenReturn(Optional.of(cancelledOrder));

        assertThatThrownBy(() -> orderQueryService.getPayableOrder(5L))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("cannot be paid");
    }

    // ======================== getOrderAmount ========================

    @Test
    @DisplayName("getOrderAmount returns payable amount")
    void testGetOrderAmount_returnsPayableAmount() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

        BigDecimal amount = orderQueryService.getOrderAmount(1L);

        assertThat(amount).isEqualTo(new BigDecimal("97.00"));
    }

    @Test
    @DisplayName("getOrderAmount throws ResourceNotFoundException for non-existing order")
    void testGetOrderAmount_notFound_throwsException() {
        when(orderRepository.findById(999L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> orderQueryService.getOrderAmount(999L))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    // ======================== verifyPurchase ========================

    @Test
    @DisplayName("verifyPurchase returns purchased=true when DELIVERED order contains product")
    void testVerifyPurchase_deliveredWithProduct_returnsTrue() {
        OrderItem item = new OrderItem();
        item.setSkuId(50L);
        item.setOrderId(3L);

        SkuDto sku = new SkuDto();
        sku.setSkuId(50L);
        sku.setSpuId(200L);

        Page<Order> orderPage = new PageImpl<>(List.of(deliveredOrder));
        when(orderRepository.findByUserId(eq(100L), any(PageRequest.class))).thenReturn(orderPage);
        when(orderItemRepository.findByOrderId(3L)).thenReturn(List.of(item));
        when(productQueryService.getSku(50L)).thenReturn(sku);

        VerifyPurchaseResponse response = orderQueryService.verifyPurchase(100L, 200L);

        assertThat(response.isPurchased()).isTrue();
        assertThat(response.getOrderId()).isEqualTo(3L);
    }

    @Test
    @DisplayName("verifyPurchase also matches when productId is the SKU id itself")
    void testVerifyPurchase_matchesBySkuId_returnsTrue() {
        OrderItem item = new OrderItem();
        item.setSkuId(200L);
        item.setOrderId(3L);

        SkuDto sku = new SkuDto();
        sku.setSkuId(200L);
        sku.setSpuId(999L); // SPU id differs from the queried product id

        Page<Order> orderPage = new PageImpl<>(List.of(deliveredOrder));
        when(orderRepository.findByUserId(eq(100L), any(PageRequest.class))).thenReturn(orderPage);
        when(orderItemRepository.findByOrderId(3L)).thenReturn(List.of(item));
        when(productQueryService.getSku(200L)).thenReturn(sku);

        // The frozen contract's productId may be an SPU id or an SKU id; here it
        // matches the purchased item's SKU id even though the SPU id differs.
        VerifyPurchaseResponse response = orderQueryService.verifyPurchase(100L, 200L);

        assertThat(response.isPurchased()).isTrue();
        assertThat(response.getOrderId()).isEqualTo(3L);
    }

    @Test
    @DisplayName("verifyPurchase returns purchased=false when no order contains product")
    void testVerifyPurchase_noMatchingProduct_returnsFalse() {
        OrderItem item = new OrderItem();
        item.setSkuId(50L);
        item.setOrderId(3L);

        SkuDto sku = new SkuDto();
        sku.setSkuId(50L);
        sku.setSpuId(999L); // Different product

        Page<Order> orderPage = new PageImpl<>(List.of(deliveredOrder));
        when(orderRepository.findByUserId(eq(100L), any(PageRequest.class))).thenReturn(orderPage);
        when(orderItemRepository.findByOrderId(3L)).thenReturn(List.of(item));
        when(productQueryService.getSku(50L)).thenReturn(sku);

        VerifyPurchaseResponse response = orderQueryService.verifyPurchase(100L, 200L);

        assertThat(response.isPurchased()).isFalse();
    }

    @Test
    @DisplayName("verifyPurchase skips non-DELIVERED and non-COMPLETED orders")
    void testVerifyPurchase_skipsNonDeliveredOrders() {
        Page<Order> orderPage = new PageImpl<>(List.of(order)); // CREATED order
        when(orderRepository.findByUserId(eq(100L), any(PageRequest.class))).thenReturn(orderPage);

        VerifyPurchaseResponse response = orderQueryService.verifyPurchase(100L, 200L);

        assertThat(response.isPurchased()).isFalse();
        verify(orderItemRepository, never()).findByOrderId(any());
    }

    // ======================== markAsPaid ========================

    @Test
    @DisplayName("markAsPaid transitions CREATED order to PAID")
    void testMarkAsPaid_created_transitionsToPaid() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

        orderQueryService.markAsPaid(1L, "PAY202606070001");

        assertThat(order.getStatus()).isEqualTo(OrderStatus.PAID);
        assertThat(order.getPaymentNo()).isEqualTo("PAY202606070001");
        assertThat(order.getPaidAmount()).isEqualTo(new BigDecimal("97.00"));
        verify(orderRepository).save(order);
    }

    @Test
    @DisplayName("markAsPaid throws 409 ORDER_STATUS_CONFLICT for SHIPPED order")
    void testMarkAsPaid_shipped_throwsException() {
        Order shippedOrder = new Order();
        shippedOrder.setId(6L);
        shippedOrder.setStatus(OrderStatus.SHIPPED);
        when(orderRepository.findById(6L)).thenReturn(Optional.of(shippedOrder));

        // A non-payable status is a frozen-contract status conflict
        // (README §7.2 ORDER_STATUS_CONFLICT / 409), guarded explicitly before
        // the state machine chain runs.
        assertThatThrownBy(() -> orderQueryService.markAsPaid(6L, "PAY001"))
                .isInstanceOf(ConflictException.class)
                .hasMessageContaining("cannot be marked paid");

        verify(eventPublisher, never()).publish(any());
    }

    @Test
    @DisplayName("markAsPaid throws 409 ORDER_STATUS_CONFLICT for CANCELLED order")
    void testMarkAsPaid_cancelled_throwsConflict() {
        Order cancelledOrder = new Order();
        cancelledOrder.setId(8L);
        cancelledOrder.setStatus(OrderStatus.CANCELLED);
        when(orderRepository.findById(8L)).thenReturn(Optional.of(cancelledOrder));

        assertThatThrownBy(() -> orderQueryService.markAsPaid(8L, "PAY008"))
                .isInstanceOf(ConflictException.class)
                .hasMessageContaining("cannot be marked paid");

        verify(orderRepository, never()).save(any(Order.class));
        verify(eventPublisher, never()).publish(any());
    }

    // ======================== markAsPaid publishes OrderPaidEvent ========================

    @Test
    @DisplayName("markAsPaid publishes the shared common OrderPaidEvent with order items")
    void testMarkAsPaid_publishesOrderPaidEvent() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

        OrderItem item = new OrderItem();
        item.setSkuId(50L);
        item.setQuantity(2);
        item.setPrice(new BigDecimal("48.50"));
        when(orderItemRepository.findByOrderId(1L)).thenReturn(List.of(item));

        orderQueryService.markAsPaid(1L, "PAY202606070001");

        ArgumentCaptor<OrderPaidEvent> captor = ArgumentCaptor.forClass(OrderPaidEvent.class);
        verify(eventPublisher).publish(captor.capture());

        OrderPaidEvent event = captor.getValue();
        assertThat(event.getOrderId()).isEqualTo(1L);
        assertThat(event.getUserId()).isEqualTo(100L);
        assertThat(event.getPaidAmount()).isEqualTo(new BigDecimal("97.00"));
        assertThat(event.getItems()).hasSize(1);
        assertThat(event.getItems().get(0).getSkuId()).isEqualTo(50L);
        assertThat(event.getItems().get(0).getQuantity()).isEqualTo(2);
    }

    @Test
    @DisplayName("markAsPaid on a PAYING order transitions to PAID and publishes the event")
    void testMarkAsPaid_paying_transitionsToPaidAndPublishes() {
        Order payingOrder = new Order();
        payingOrder.setId(7L);
        payingOrder.setUserId(100L);
        payingOrder.setStatus(OrderStatus.PAYING);
        payingOrder.setPayableAmount(new BigDecimal("50.00"));
        when(orderRepository.findById(7L)).thenReturn(Optional.of(payingOrder));

        orderQueryService.markAsPaid(7L, "PAY007");

        assertThat(payingOrder.getStatus()).isEqualTo(OrderStatus.PAID);
        verify(eventPublisher).publish(any(OrderPaidEvent.class));
    }
}
