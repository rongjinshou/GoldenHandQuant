package com.ecommerce.payment.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.payment.dto.PaymentCallbackRequest;
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

import java.math.BigDecimal;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link PaymentCallbackService}.
 *
 * <p>{@code processCallback()} verifies the {@code X-Payment-Signature}
 * header against the mock "valid-signature" value before doing anything
 * else (design-docs/02 §8.4), and is idempotent per callbackSequence and
 * per terminal status (SUCCESS/FAILED).
 */
@ExtendWith(MockitoExtension.class)
class PaymentCallbackServiceTest {

    @Mock
    private PaymentRecordRepository paymentRecordRepository;

    @Mock
    private OrderPaymentStatusUpdater orderPaymentStatusUpdater;

    @Mock
    private PaymentService paymentService;

    private PaymentCallbackService callbackService;

    @BeforeEach
    void setUp() {
        callbackService = new PaymentCallbackService(
                paymentRecordRepository,
                orderPaymentStatusUpdater,
                paymentService
        );
    }

    // ---- testProcessCallback_invalidSignature_throwsAuthorizationException ----

    @Test
    @DisplayName("callback with an invalid signature is rejected before any processing")
    void testProcessCallback_invalidSignature_throwsAuthorizationException() {
        // Given: a callback with an obviously forged/wrong signature
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY001", 1L, "SUCCESS",
                new BigDecimal("99.00"), "seq-001",
                null // signature travels via header, not the body, in production
        );

        // When/Then: an invalid signature is rejected up front
        AuthorizationException ex = assertThrows(AuthorizationException.class,
                () -> callbackService.processCallback(request, "WRONG_SIGNATURE_FORGED"));
        assertEquals("UNAUTHORIZED", ex.getCode());

        // And no state-changing work ever happens
        verify(paymentRecordRepository, never()).findByPaymentNo(any());
        verify(paymentRecordRepository, never()).save(any());
        verify(orderPaymentStatusUpdater, never()).markAsPaid(any(), any());
        verify(paymentService, never()).confirmPayment(any());
    }

    // ---- testProcessCallback_updatesPaymentStatus ----

    @Test
    @DisplayName("successful callback updates payment status to SUCCESS")
    void testProcessCallback_updatesPaymentStatus() {
        // Given
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY002", 2L, "SUCCESS",
                new BigDecimal("199.00"), "seq-002", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY002");
        payment.setOrderId(2L);
        payment.setPaidAmount(new BigDecimal("199.00"));
        payment.setStatus(PaymentStatus.CREATED);

        when(paymentRecordRepository.findByPaymentNo("PAY002"))
                .thenReturn(Optional.of(payment));
        when(paymentRecordRepository.save(any(PaymentRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        callbackService.processCallback(request, "valid-signature");

        // Then: payment status should be updated to SUCCESS
        ArgumentCaptor<PaymentRecord> captor = ArgumentCaptor.forClass(PaymentRecord.class);
        verify(paymentRecordRepository).save(captor.capture());
        PaymentRecord saved = captor.getValue();
        assertEquals(PaymentStatus.SUCCESS, saved.getStatus());
        assertEquals(new BigDecimal("199.00"), saved.getPaidAmount());
        assertEquals("seq-002", saved.getCallbackSequence());
        assertNotNull(saved.getPaidAt());
    }

    // ---- testProcessCallback_duplicateCallback_handledIdempotently ----

    @Test
    @DisplayName("duplicate callback with same sequence is handled idempotently")
    void testProcessCallback_duplicateCallback_handledIdempotently() {
        // Given: payment already has the same callback sequence
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY003", 3L, "SUCCESS",
                new BigDecimal("299.00"), "seq-003", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY003");
        payment.setOrderId(3L);
        payment.setPaidAmount(new BigDecimal("299.00"));
        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setCallbackSequence("seq-003"); // already processed with this sequence

        when(paymentRecordRepository.findByPaymentNo("PAY003"))
                .thenReturn(Optional.of(payment));

        // When: same callback sequence arrives again
        callbackService.processCallback(request, "valid-signature");

        // Then: idempotent — no save, no confirm, no status update
        verify(paymentRecordRepository, never()).save(any());
        verify(paymentService, never()).confirmPayment(any());
        verify(orderPaymentStatusUpdater, never()).markAsPaid(any(), any());
    }

    // ---- testProcessFailedCallback_duplicateFailedCallback_isIdempotentNoOp ----

    @Test
    @DisplayName("a second FAILED callback for an already-FAILED payment is an idempotent no-op")
    void testProcessFailedCallback_duplicateFailedCallback_isIdempotentNoOp() {
        // Given: payment already FAILED (e.g. from an earlier callback with a
        // different callbackSequence, so the generic sequence-based guard
        // in processCallback() does not catch this case)
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY004", 4L, "FAILED",
                new BigDecimal("50.00"), "seq-004-retry", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY004");
        payment.setOrderId(4L);
        payment.setStatus(PaymentStatus.FAILED);
        payment.setCallbackSequence("seq-004-original");

        when(paymentRecordRepository.findByPaymentNo("PAY004"))
                .thenReturn(Optional.of(payment));

        // When: a second FAILED callback (different sequence) arrives
        callbackService.processCallback(request, "valid-signature");

        // Then: idempotent no-op — no save, no order-status update
        verify(paymentRecordRepository, never()).save(any());
        verify(orderPaymentStatusUpdater, never()).markPaymentFailed(any());
    }
}
