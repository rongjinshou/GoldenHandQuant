package com.ecommerce.payment.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.PaymentSucceededEvent;
import com.ecommerce.common.test.FaultInjectionRegistry;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.order.query.OrderQueryService;
import com.ecommerce.payment.dto.PayRequest;
import com.ecommerce.payment.dto.PayResponse;
import com.ecommerce.payment.entity.PaymentMethod;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link PaymentService}: order lookup for {@code pay()}, and
 * {@code confirmPayment()}'s narrowed responsibility of publishing
 * {@link PaymentSucceededEvent} (design-docs/02 §6.2 — logistics/loyalty/
 * notification reactions live in async listeners, not here).
 */
@ExtendWith(MockitoExtension.class)
class PaymentServiceTest {

    @Mock
    private PaymentRecordRepository paymentRecordRepository;

    @Mock
    private PaymentValidator paymentValidator;

    @Mock
    private DomainEventPublisher eventPublisher;

    @Mock
    private OrderPaymentStatusUpdater orderPaymentStatusUpdater;

    @Mock
    private OrderQueryService orderQueryService;

    @Mock
    private JdbcTemplate jdbcTemplate;

    private PaymentService paymentService;

    @BeforeEach
    void setUp() {
        paymentService = new PaymentService(
                paymentRecordRepository,
                paymentValidator,
                eventPublisher,
                orderPaymentStatusUpdater,
                orderQueryService,
                jdbcTemplate
        );
    }

    // ---- testPay_validRequest_createsPaymentRecord ----

    @Test
    @DisplayName("pay() should create a PaymentRecord for a valid request")
    void testPay_validRequest_createsPaymentRecord() {
        // Given
        PayRequest request = new PayRequest(1L, new BigDecimal("99.00"),
                PaymentMethod.ALIPAY, "CLIENT123");

        OrderDto orderDto = new OrderDto();
        orderDto.setOrderId(1L);
        orderDto.setOrderNo("ORD001");
        orderDto.setUserId(100L);
        orderDto.setPayableAmount(new BigDecimal("99.00"));
        orderDto.setStatus(com.ecommerce.order.entity.OrderStatus.CREATED);

        // JdbcTemplate is used directly to query order
        when(jdbcTemplate.queryForObject(anyString(), any(RowMapper.class), eq(1L)))
                .thenReturn(orderDto);

        PaymentRecord savedRecord = new PaymentRecord();
        savedRecord.setPaymentNo("PAY123");
        savedRecord.setOrderId(1L);
        savedRecord.setPaidAmount(new BigDecimal("99.00"));
        savedRecord.setStatus(PaymentStatus.CREATED);
        when(paymentRecordRepository.save(any(PaymentRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        PayResponse response = paymentService.pay(request);

        // Then
        assertNotNull(response);
        assertEquals(1L, response.getOrderId());
        assertEquals(PaymentStatus.CREATED, response.getStatus());
        assertEquals(new BigDecimal("99.00"), response.getPaidAmount());
        assertNotNull(response.getPaymentNo());

        // Verify JdbcTemplate was used directly to query order
        verify(jdbcTemplate).queryForObject(anyString(), any(RowMapper.class), eq(1L));
        // Verify OrderQueryService was NOT used (bypasses interface)
        verify(orderQueryService, never()).getPayableOrder(any());
        verify(orderQueryService, never()).getOrder(any());

        // Verify payment was saved
        verify(paymentRecordRepository).save(any(PaymentRecord.class));
        verify(paymentValidator).validate(eq(request), eq(orderDto));
    }

    // ---- confirmPayment_publishesPaymentSucceededEvent_withCorrectFields ----

    @Test
    @DisplayName("confirmPayment() publishes PaymentSucceededEvent with paymentNo/orderId/paidAmount/paidAt")
    void confirmPayment_publishesPaymentSucceededEvent_withCorrectFields() {
        // Given: a payment record already marked SUCCESS by the caller
        // (PaymentCallbackService.processSuccessCallback), as confirmPayment()
        // itself no longer sets payment/order status or deducts inventory —
        // see the class Javadoc on PaymentService.confirmPayment().
        LocalDateTime paidAt = LocalDateTime.now();
        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY001");
        payment.setOrderId(1L);
        payment.setPaidAmount(new BigDecimal("99.00"));
        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setPaidAt(paidAt);

        // When: confirmPayment is called
        paymentService.confirmPayment(payment);

        // Then: only the event is published — no notification/logistics/
        // loyalty side effects run synchronously inside this method.
        ArgumentCaptor<PaymentSucceededEvent> eventCaptor =
                ArgumentCaptor.forClass(PaymentSucceededEvent.class);
        verify(eventPublisher).publish(eventCaptor.capture());

        PaymentSucceededEvent event = eventCaptor.getValue();
        assertEquals("PAY001", event.getPaymentNo());
        assertEquals(1L, event.getOrderId());
        assertEquals(new BigDecimal("99.00"), event.getPaidAmount());
        assertEquals(paidAt, event.getPaidAt());
    }

    // ---- confirmPayment_notificationFaultInjected_stillSucceeds (PUB-108-shaped) ----

    @Test
    @DisplayName("confirmPayment() succeeds regardless of notification fault injection")
    void confirmPayment_notificationFaultInjected_stillSucceeds() {
        // Given: the notification-send fault is active — confirmPayment() no
        // longer has any dependency that could be affected by it, since
        // notification sending was moved to an AFTER_COMMIT listener
        // (PaymentSucceededNotificationListener), so a listener failure can
        // never roll back payment confirmation (design-docs/09 §3, PUB-108).
        FaultInjectionRegistry.add("notification-send-failure");
        try {
            PaymentRecord payment = new PaymentRecord();
            payment.setPaymentNo("PAY001");
            payment.setOrderId(1L);
            payment.setPaidAmount(new BigDecimal("99.00"));
            payment.setStatus(PaymentStatus.SUCCESS);
            payment.setPaidAt(LocalDateTime.now());

            assertDoesNotThrow(() -> paymentService.confirmPayment(payment));

            verify(eventPublisher).publish(any());
        } finally {
            FaultInjectionRegistry.clear();
        }
    }

    // ---- testConfirmPayment_usesJdbcTemplate ----

    @Test
    @DisplayName("pay() queries order data for payment")
    void testConfirmPayment_usesJdbcTemplate() {
        // Given
        PayRequest request = new PayRequest(1L, new BigDecimal("50.00"),
                PaymentMethod.WECHAT, "CLIENT456");

        OrderDto orderDto = new OrderDto();
        orderDto.setOrderId(1L);
        orderDto.setPayableAmount(new BigDecimal("50.00"));
        orderDto.setStatus(com.ecommerce.order.entity.OrderStatus.CREATED);

        // JdbcTemplate is used directly
        when(jdbcTemplate.queryForObject(anyString(), any(RowMapper.class), eq(1L)))
                .thenReturn(orderDto);
        when(paymentRecordRepository.save(any(PaymentRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        paymentService.pay(request);

        // Then: JdbcTemplate is called directly
        // Verify order lookup dependencies.
        verify(jdbcTemplate, times(1)).queryForObject(anyString(), any(RowMapper.class), eq(1L));
        verify(orderQueryService, never()).getPayableOrder(any());
        verify(orderQueryService, never()).getOrder(any());
    }

    // ---- testGetPayment_returnsPaymentRecord ----

    @Test
    @DisplayName("getPayment() should return PaymentRecord by paymentNo")
    void testGetPayment_returnsPaymentRecord() {
        // Given
        String paymentNo = "PAY123";
        PaymentRecord record = new PaymentRecord();
        record.setPaymentNo(paymentNo);
        record.setOrderId(1L);
        record.setPaidAmount(new BigDecimal("99.00"));
        record.setStatus(PaymentStatus.SUCCESS);
        record.setCreatedAt(java.time.LocalDateTime.now());

        when(paymentRecordRepository.findByPaymentNo(paymentNo))
                .thenReturn(Optional.of(record));

        // When
        PayResponse response = paymentService.getPayment(paymentNo);

        // Then
        assertNotNull(response);
        assertEquals(paymentNo, response.getPaymentNo());
        assertEquals(1L, response.getOrderId());
        assertEquals(PaymentStatus.SUCCESS, response.getStatus());
        assertEquals(new BigDecimal("99.00"), response.getPaidAmount());
    }
}
