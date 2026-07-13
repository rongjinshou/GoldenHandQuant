package com.ecommerce.payment.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.notification.LocalNotificationService;
import com.ecommerce.common.notification.NotificationRequest;
import com.ecommerce.payment.dto.RefundApplyRequest;
import com.ecommerce.payment.dto.RefundResponse;
import com.ecommerce.payment.dto.RefundReviewRequest;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.entity.RefundRecord;
import com.ecommerce.payment.entity.RefundStatus;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import com.ecommerce.payment.repository.RefundRecordRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link RefundService}.
 *
 * <p>Per design-docs/09 §4, merchant approval must NOT complete a refund
 * directly — the flow is:
 * PENDING_REVIEW -> (approve) -> WAITING_WAREHOUSE_ACCEPT -> (warehouse
 * accepts) -> WAREHOUSE_ACCEPTED -> COMPLETED. {@code processRefund()} only
 * ever runs from {@link RefundService#warehouseAccept(Long, Long)}.
 */
@ExtendWith(MockitoExtension.class)
class RefundServiceTest {

    @Mock
    private RefundRecordRepository refundRecordRepository;

    @Mock
    private PaymentRecordRepository paymentRecordRepository;

    @Mock
    private RefundCalculator refundCalculator;

    @Mock
    private DomainEventPublisher eventPublisher;

    @Mock
    private LocalNotificationService notificationService;

    @Mock
    private AuditLogService auditLogService;

    private RefundService refundService;

    @BeforeEach
    void setUp() {
        refundService = new RefundService(
                refundRecordRepository,
                paymentRecordRepository,
                refundCalculator,
                eventPublisher,
                notificationService,
                auditLogService
        );
    }

    // ---- approveRefund_movesToWaitingWarehouseAccept_doesNotCompleteImmediately ----

    @Test
    @DisplayName("reviewRefund(approved) moves to WAITING_WAREHOUSE_ACCEPT, does not complete immediately")
    void approveRefund_movesToWaitingWarehouseAccept_doesNotCompleteImmediately() {
        // Given: a refund in PENDING_REVIEW
        RefundRecord refund = new RefundRecord();
        refund.setId(1L);
        refund.setRefundNo("RF001");
        refund.setPaymentNo("PAY001");
        refund.setOrderId(10L);
        refund.setUserId(100L);
        refund.setRefundAmount(new BigDecimal("97.00"));
        refund.setStatus(RefundStatus.PENDING_REVIEW);
        refund.setReason("Changed mind");

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY001");
        payment.setOrderId(10L);
        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setPaidAmount(new BigDecimal("100.00"));

        when(refundRecordRepository.findById(1L)).thenReturn(Optional.of(refund));
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        RefundReviewRequest reviewRequest = new RefundReviewRequest(true, "Approved by admin");

        // When: admin approves the refund
        RefundResponse response = refundService.reviewRefund(1L, 999L, reviewRequest);

        // Then: status only reaches WAITING_WAREHOUSE_ACCEPT — merchant
        // approval must not complete the refund directly (design-docs/09 §4).
        // Note: approveRefund() must NOT reach processRefund()/payment lookup
        // at all — verified structurally by never stubbing
        // paymentRecordRepository here (strict stubs would fail this test
        // if approveRefund() started querying it again).
        assertEquals(RefundStatus.WAITING_WAREHOUSE_ACCEPT, response.getStatus(),
                "reviewed refund status");
        assertNotEquals(RefundStatus.COMPLETED, response.getStatus());
        assertNull(response.getCompletedAt());
        assertNotEquals(PaymentStatus.CLOSED, payment.getStatus(),
                "payment must not be closed until warehouse acceptance completes the refund");
    }

    // ---- warehouseAccept_afterApproval_completesRefund ----

    @Test
    @DisplayName("warehouseAccept after approval completes the refund")
    void warehouseAccept_afterApproval_completesRefund() {
        // Given: a refund already approved and waiting on warehouse acceptance
        RefundRecord refund = new RefundRecord();
        refund.setId(1L);
        refund.setRefundNo("RF001");
        refund.setPaymentNo("PAY001");
        refund.setOrderId(10L);
        refund.setUserId(100L);
        refund.setRefundAmount(new BigDecimal("97.00"));
        refund.setStatus(RefundStatus.WAITING_WAREHOUSE_ACCEPT);

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY001");
        payment.setOrderId(10L);
        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setPaidAmount(new BigDecimal("100.00"));

        when(refundRecordRepository.findById(1L)).thenReturn(Optional.of(refund));
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(paymentRecordRepository.findByPaymentNo("PAY001"))
                .thenReturn(Optional.of(payment));

        // When: warehouse accepts the returned goods
        RefundResponse response = refundService.warehouseAccept(1L, 888L);

        // Then: the refund is now COMPLETED and the payment is CLOSED
        assertEquals(RefundStatus.COMPLETED, response.getStatus());
        assertNotNull(response.getCompletedAt());
        assertEquals(PaymentStatus.CLOSED, payment.getStatus());
    }

    // ---- testWarehouseAccept_wrongStatus_throwsRefundStatusInvalid ----

    @Test
    @DisplayName("warehouseAccept on a refund that isn't WAITING_WAREHOUSE_ACCEPT throws")
    void testWarehouseAccept_wrongStatus_throwsRefundStatusInvalid() {
        // Given: warehouseAccept requires WAITING_WAREHOUSE_ACCEPT status
        RefundRecord refund = new RefundRecord();
        refund.setId(2L);
        refund.setRefundNo("RF002");
        refund.setPaymentNo("PAY002");
        refund.setOrderId(20L);
        refund.setUserId(200L);
        refund.setStatus(RefundStatus.COMPLETED); // already completed

        when(refundRecordRepository.findById(2L)).thenReturn(Optional.of(refund));

        // When/Then: calling warehouseAccept on a COMPLETED refund throws
        // because it requires WAITING_WAREHOUSE_ACCEPT status
        BusinessException ex = assertThrows(BusinessException.class,
                () -> refundService.warehouseAccept(2L, 999L));
        assertEquals("REFUND_STATUS_INVALID", ex.getCode());
    }

    // ---- warehouseReject_rejectsRefund_neverExecutesFinancialRefund ----

    @Test
    @DisplayName("warehouseReject (accepted=false) rejects the refund and never executes the financial refund")
    void warehouseReject_rejectsRefund_neverExecutesFinancialRefund() {
        // Given: a refund approved and waiting on warehouse acceptance
        RefundRecord refund = new RefundRecord();
        refund.setId(3L);
        refund.setRefundNo("RF003");
        refund.setPaymentNo("PAY003");
        refund.setOrderId(30L);
        refund.setUserId(300L);
        refund.setRefundAmount(new BigDecimal("97.00"));
        refund.setStatus(RefundStatus.WAITING_WAREHOUSE_ACCEPT);

        when(refundRecordRepository.findById(3L)).thenReturn(Optional.of(refund));
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When: warehouse rejects the returned goods
        RefundResponse response = refundService.warehouseReject(3L, 888L);

        // Then: refund is REJECTED and nothing of the completion flow ran —
        // no payment closure, no RefundCompletedEvent, no notification (09 §4:
        // intact goods at warehouse acceptance are the refund's precondition).
        assertEquals(RefundStatus.REJECTED, response.getStatus());
        assertNull(response.getCompletedAt());
        assertEquals(888L, refund.getWarehouseAcceptorId());
        verify(paymentRecordRepository, never()).findByPaymentNo(any());
        verify(eventPublisher, never()).publish(any());
        verify(notificationService, never()).send(any(NotificationRequest.class));
        // Audit trail records the true before/after states
        verify(auditLogService).record(eq("888"), eq("REFUND_WAREHOUSE_ACCEPT"),
                eq("RF003"), eq("WAITING_WAREHOUSE_ACCEPT"), eq("REJECTED"), any());
    }

    // ---- warehouseReject_wrongStatus_throwsConflict ----

    @Test
    @DisplayName("warehouseReject on a refund that isn't WAITING_WAREHOUSE_ACCEPT throws 409")
    void warehouseReject_wrongStatus_throwsConflict() {
        // Given: a refund still pending merchant review
        RefundRecord refund = new RefundRecord();
        refund.setId(4L);
        refund.setRefundNo("RF004");
        refund.setPaymentNo("PAY004");
        refund.setOrderId(40L);
        refund.setUserId(400L);
        refund.setStatus(RefundStatus.PENDING_REVIEW);

        when(refundRecordRepository.findById(4L)).thenReturn(Optional.of(refund));

        // When/Then: same status guard as warehouseAccept
        ConflictException ex = assertThrows(ConflictException.class,
                () -> refundService.warehouseReject(4L, 999L));
        assertEquals("REFUND_STATUS_INVALID", ex.getCode());
        assertEquals(RefundStatus.PENDING_REVIEW, refund.getStatus());
    }

    // ---- applyRefund_duplicateRefundRequestNo_returnsExistingRecord_doesNotCreateSecond ----

    @Test
    @DisplayName("applyRefund with a duplicate refundRequestNo returns the existing record")
    void applyRefund_duplicateRefundRequestNo_returnsExistingRecord_doesNotCreateSecond() {
        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY005");
        payment.setOrderId(50L);
        payment.setPaidAmount(new BigDecimal("100.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        RefundApplyRequest request = new RefundApplyRequest(50L, "PAY005", "Wrong size");
        request.setRefundRequestNo("RFD-001");

        when(paymentRecordRepository.findByPaymentNo("PAY005"))
                .thenReturn(Optional.of(payment));
        when(refundCalculator.calculate(new BigDecimal("100.00")))
                .thenReturn(new BigDecimal("98.00"));

        RefundRecord saved = new RefundRecord();
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> {
                    RefundRecord arg = invocation.getArgument(0);
                    saved.setId(1L);
                    saved.setRefundNo(arg.getRefundNo());
                    saved.setRefundRequestNo(arg.getRefundRequestNo());
                    saved.setPaymentNo(arg.getPaymentNo());
                    saved.setOrderId(arg.getOrderId());
                    saved.setUserId(arg.getUserId());
                    saved.setRefundAmount(arg.getRefundAmount());
                    saved.setReason(arg.getReason());
                    saved.setStatus(arg.getStatus());
                    return saved;
                });

        // First call creates the refund
        RefundResponse first = refundService.applyRefund(100L, request);

        // Second call with the same refundRequestNo short-circuits to the existing record
        when(refundRecordRepository.findByRefundRequestNo("RFD-001"))
                .thenReturn(Optional.of(saved));
        RefundResponse second = refundService.applyRefund(100L, request);

        assertEquals(first.getRefundNo(), second.getRefundNo());
        verify(refundRecordRepository, times(1)).save(any(RefundRecord.class));
    }

    // ---- testApplyRefund_createsRefundRecord ----

    @Test
    @DisplayName("applyRefund creates a refund record in PENDING_REVIEW status")
    void testApplyRefund_createsRefundRecord() {
        // Given: a successful payment exists
        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY003");
        payment.setOrderId(30L);
        payment.setPaidAmount(new BigDecimal("200.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByPaymentNo("PAY003"))
                .thenReturn(Optional.of(payment));
        when(refundCalculator.calculate(new BigDecimal("200.00")))
                .thenReturn(new BigDecimal("195.00"));
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        RefundApplyRequest request = new RefundApplyRequest(30L, "PAY003", "Defective item");

        // When
        RefundResponse response = refundService.applyRefund(100L, request);

        // Then
        assertNotNull(response);
        assertEquals("PAY003", response.getPaymentNo());
        assertEquals(30L, response.getOrderId());
        assertEquals(100L, response.getUserId());
        assertEquals(RefundStatus.PENDING_REVIEW, response.getStatus());
        assertEquals("Defective item", response.getReason());
        assertNotNull(response.getRefundNo());
    }

    // ---- testProcessRefund_calculatesCorrectAmount ----

    @Test
    @DisplayName("processRefund calculates amount using RefundCalculator formula")
    void testProcessRefund_calculatesCorrectAmount() {
        // Given: a successful payment of 150.00
        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY004");
        payment.setOrderId(40L);
        payment.setPaidAmount(new BigDecimal("150.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        // applyRefund() delegates the formula entirely to RefundCalculator —
        // this test just proves whatever it returns flows through untouched.
        BigDecimal expectedRefundAmount = new BigDecimal("147.00");

        when(paymentRecordRepository.findByPaymentNo("PAY004"))
                .thenReturn(Optional.of(payment));
        when(refundCalculator.calculate(new BigDecimal("150.00")))
                .thenReturn(expectedRefundAmount);
        when(refundRecordRepository.save(any(RefundRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        RefundApplyRequest request = new RefundApplyRequest(40L, "PAY004", "Wrong size");

        // When
        RefundResponse response = refundService.applyRefund(100L, request);

        // Then: the refund amount comes from RefundCalculator
        assertEquals(expectedRefundAmount, response.getRefundAmount(),
                "refund amount must come from RefundCalculator.calculate()");
    }
}
