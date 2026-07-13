package com.ecommerce.payment.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
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
        payment.setOrderAmount(new BigDecimal("199.00"));
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

    // ---- testProcessCallback_amountMismatch_rejected ----

    @Test
    @DisplayName("successful callback whose amount differs from the locked order amount is rejected (PAYMENT_AMOUNT_MISMATCH)")
    void testProcessCallback_amountMismatch_rejected() {
        // Given: the payment locked orderAmount=199.00 at pay() time, but the
        // callback arrives claiming a higher amount (design-docs/09 §2).
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY005", 5L, "SUCCESS",
                new BigDecimal("999.00"), "seq-005", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY005");
        payment.setOrderId(5L);
        payment.setOrderAmount(new BigDecimal("199.00"));
        payment.setPaidAmount(new BigDecimal("199.00"));
        payment.setStatus(PaymentStatus.CREATED);

        when(paymentRecordRepository.findByPaymentNo("PAY005"))
                .thenReturn(Optional.of(payment));

        // When/Then: the mismatched callback amount is rejected and nothing is
        // marked SUCCESS nor propagated downstream.
        BusinessException ex = assertThrows(BusinessException.class,
                () -> callbackService.processCallback(request, "valid-signature"));
        assertEquals("PAYMENT_AMOUNT_MISMATCH", ex.getCode());

        verify(paymentRecordRepository, never()).save(any());
        verify(orderPaymentStatusUpdater, never()).markAsPaid(any(), any());
        verify(paymentService, never()).confirmPayment(any());
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

    // ---- testProcessCallback_successOnClosedPayment_throwsStatusConflict ----

    @Test
    @DisplayName("a SUCCESS callback for a CLOSED (refunded) payment is rejected with 409 PAYMENT_STATUS_CONFLICT")
    void testProcessCallback_successOnClosedPayment_throwsStatusConflict() {
        // Given: the payment was refunded and CLOSED (terminal state, 附录C)
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY006", 6L, "SUCCESS",
                new BigDecimal("100.00"), "seq-006-late", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY006");
        payment.setOrderId(6L);
        payment.setOrderAmount(new BigDecimal("100.00"));
        payment.setPaidAmount(new BigDecimal("100.00"));
        payment.setStatus(PaymentStatus.CLOSED);
        payment.setCallbackSequence("seq-006-original");

        when(paymentRecordRepository.findByPaymentNo("PAY006"))
                .thenReturn(Optional.of(payment));

        // When/Then: the late SUCCESS callback must not resurrect the payment
        ConflictException ex = assertThrows(ConflictException.class,
                () -> callbackService.processCallback(request, "valid-signature"));
        assertEquals("PAYMENT_STATUS_CONFLICT", ex.getCode());

        assertEquals(PaymentStatus.CLOSED, payment.getStatus());
        verify(paymentRecordRepository, never()).save(any());
        verify(orderPaymentStatusUpdater, never()).markAsPaid(any(), any());
        verify(paymentService, never()).confirmPayment(any());
    }

    // ---- testProcessFailedCallback_onClosedPayment_isNoOp_neverFlipsToFailed ----

    @Test
    @DisplayName("a FAILED callback for a CLOSED (refunded) payment is a no-op and never flips CLOSED to FAILED")
    void testProcessFailedCallback_onClosedPayment_isNoOp_neverFlipsToFailed() {
        // Given: the payment was refunded and CLOSED; a stray FAILED callback
        // arrives with a fresh callbackSequence (so the generic sequence-based
        // idempotency guard does not catch it)
        PaymentCallbackRequest request = new PaymentCallbackRequest(
                "PAY007", 7L, "FAILED",
                new BigDecimal("100.00"), "seq-007-late", null
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY007");
        payment.setOrderId(7L);
        payment.setStatus(PaymentStatus.CLOSED);
        payment.setCallbackSequence("seq-007-original");

        when(paymentRecordRepository.findByPaymentNo("PAY007"))
                .thenReturn(Optional.of(payment));

        // When: the stray FAILED callback is processed
        callbackService.processCallback(request, "valid-signature");

        // Then: no-op — status stays CLOSED, nothing saved, order untouched
        assertEquals(PaymentStatus.CLOSED, payment.getStatus());
        verify(paymentRecordRepository, never()).save(any());
        verify(orderPaymentStatusUpdater, never()).markPaymentFailed(any());
    }
}
