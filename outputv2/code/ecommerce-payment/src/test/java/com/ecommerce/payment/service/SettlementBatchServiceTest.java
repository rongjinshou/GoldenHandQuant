package com.ecommerce.payment.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.payment.dto.SettlementBatchResponse;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.entity.RefundRecord;
import com.ecommerce.payment.entity.RefundStatus;
import com.ecommerce.payment.entity.SettlementBatch;
import com.ecommerce.payment.entity.SettlementStatus;
import com.ecommerce.payment.repository.InvoiceRecordRepository;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import com.ecommerce.payment.repository.RefundRecordRepository;
import com.ecommerce.payment.repository.SettlementBatchRepository;
import com.ecommerce.payment.repository.SettlementOrderItemRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link SettlementBatchService}.
 *
 * <p>Per design-docs/14 §5, a settlement batch includes the orders actually
 * paid on the batch date — payments selected by paidAt window with status IN
 * (SUCCESS, CLOSED), never PENDING/FAILED attempts — and must reflect real
 * refund totals rather than a hardcoded zero, including on days with zero
 * payments (refund-only days).
 */
@ExtendWith(MockitoExtension.class)
class SettlementBatchServiceTest {

    @Mock
    private SettlementBatchRepository settlementBatchRepository;

    @Mock
    private SettlementOrderItemRepository settlementOrderItemRepository;

    @Mock
    private PaymentRecordRepository paymentRecordRepository;

    @Mock
    private InvoiceRecordRepository invoiceRecordRepository;

    @Mock
    private RefundRecordRepository refundRecordRepository;

    @Mock
    private AuditLogService auditLogService;

    private SettlementBatchService settlementBatchService;

    @BeforeEach
    void setUp() {
        settlementBatchService = new SettlementBatchService(
                settlementBatchRepository,
                settlementOrderItemRepository,
                paymentRecordRepository,
                invoiceRecordRepository,
                refundRecordRepository,
                auditLogService
        );
    }

    // ---- testGenerateBatch_onlyIncludesSuccessPayments ----

    @Test
    @DisplayName("settlement selects payments by paidAt window with status IN (SUCCESS, CLOSED), never PENDING/FAILED")
    void testGenerateBatch_onlyIncludesSuccessPayments() {
        // Given: only successfully-paid payments (SUCCESS, or CLOSED =
        // paid-then-refunded) are returned by the status-filtered repository
        // query — PENDING/FAILED attempts never reach the service, matching
        // design-docs/14 §5 ("支付成功且未结算的订单").
        LocalDate batchDate = LocalDate.of(2026, 6, 1);

        PaymentRecord paid1 = createPayment(1L, "PAY001", new BigDecimal("100.00"), PaymentStatus.SUCCESS);
        PaymentRecord paid2 = createPayment(2L, "PAY002", new BigDecimal("200.00"), PaymentStatus.CLOSED);

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusInAndPaidAtBetween(
                eq(List.of(PaymentStatus.SUCCESS, PaymentStatus.CLOSED)), any(), any()))
                .thenReturn(Arrays.asList(paid1, paid2));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.REFUNDED), any(), any()))
                .thenReturn(Collections.emptyList());

        when(settlementBatchRepository.save(any(SettlementBatch.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate, "999");

        // Then: both successfully-paid payments (SUCCESS + CLOSED) are included
        assertNotNull(response);
        assertEquals(2, response.getOrderCount(), "settlement order count");
        assertEquals(new BigDecimal("300.00"), response.getTotalPaymentAmount(),
                "total=300 from the 2 successfully-paid payments only");

        // And the unfiltered (status-agnostic) query is never used
        verify(paymentRecordRepository, never()).findByPaidAtBetween(any(), any());
    }

    // ---- testGenerateBatch_calculatesTotals ----

    @Test
    @DisplayName("settlement batch calculates totals from the day's successfully-paid payments")
    void testGenerateBatch_calculatesTotals() {
        // Given: only successfully-paid payments are returned (status filter
        // applied at the query level)
        LocalDate batchDate = LocalDate.of(2026, 6, 2);

        PaymentRecord payment1 = createPayment(10L, "PAY010", new BigDecimal("150.00"), PaymentStatus.SUCCESS);
        PaymentRecord payment2 = createPayment(20L, "PAY020", new BigDecimal("350.00"), PaymentStatus.SUCCESS);

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusInAndPaidAtBetween(
                eq(List.of(PaymentStatus.SUCCESS, PaymentStatus.CLOSED)), any(), any()))
                .thenReturn(Arrays.asList(payment1, payment2));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.REFUNDED), any(), any()))
                .thenReturn(Collections.emptyList());

        ArgumentCaptor<SettlementBatch> batchCaptor =
                ArgumentCaptor.forClass(SettlementBatch.class);
        when(settlementBatchRepository.save(batchCaptor.capture()))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate, "999");

        // Then: totals include only the 2 successfully-paid payments
        assertEquals(2, response.getOrderCount(), "2 successfully-paid orders");
        assertEquals(new BigDecimal("500.00"), response.getTotalPaymentAmount(),
                "150+350=500");

        // Verify batch was saved with correct totals
        SettlementBatch captured = batchCaptor.getValue();
        assertEquals(batchDate, captured.getBatchDate());
        assertEquals(SettlementStatus.GENERATED, captured.getStatus());
        assertNotNull(captured.getBatchNo());
    }

    // ---- createBatch_withCompletedRefundToday_includesRefundTotal ----

    @Test
    @DisplayName("settlement includes real completed-refund totals for the batch date")
    void createBatch_withCompletedRefundToday_includesRefundTotal() {
        // Given: one SUCCESS payment and one REFUNDED refund of 30.00 on the batch date
        LocalDate batchDate = LocalDate.of(2026, 6, 3);

        PaymentRecord payment = createPayment(40L, "PAY040", new BigDecimal("100.00"), PaymentStatus.SUCCESS);

        RefundRecord refund = new RefundRecord();
        refund.setRefundNo("RF040");
        refund.setPaymentNo("PAY040");
        refund.setOrderId(40L);
        refund.setUserId(1L);
        refund.setRefundAmount(new BigDecimal("30.00"));
        refund.setStatus(RefundStatus.REFUNDED);
        refund.setCompletedAt(batchDate.atTime(10, 0));

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusInAndPaidAtBetween(
                eq(List.of(PaymentStatus.SUCCESS, PaymentStatus.CLOSED)), any(), any()))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.REFUNDED), any(), any()))
                .thenReturn(Arrays.asList(refund));

        when(settlementBatchRepository.save(any(SettlementBatch.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate, "999");

        // Then: the real refund total (30.00) is reflected, not a hardcoded zero
        assertEquals(0, new BigDecimal("30.00").compareTo(response.getTotalRefundAmount()));
    }

    // ---- generateBatch_refundOnlyDay_noPayments_stillAggregatesRefunds ----

    @Test
    @DisplayName("a day with zero payments still produces a batch carrying that day's refund totals")
    void generateBatch_refundOnlyDay_noPayments_stillAggregatesRefunds() {
        // Given: no payments at all on the batch date, but one refund
        // completed that day — there is no empty-day short-circuit
        // (design-docs/14 §5: the batch includes refund data too).
        LocalDate batchDate = LocalDate.of(2026, 6, 4);

        RefundRecord refund = new RefundRecord();
        refund.setRefundNo("RF050");
        refund.setPaymentNo("PAY050");
        refund.setOrderId(50L);
        refund.setUserId(1L);
        refund.setRefundAmount(new BigDecimal("42.00"));
        refund.setStatus(RefundStatus.REFUNDED);
        refund.setCompletedAt(batchDate.atTime(9, 30));

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusInAndPaidAtBetween(
                eq(List.of(PaymentStatus.SUCCESS, PaymentStatus.CLOSED)), any(), any()))
                .thenReturn(Collections.emptyList());
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.REFUNDED), any(), any()))
                .thenReturn(Arrays.asList(refund));
        when(settlementBatchRepository.save(any(SettlementBatch.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate, "999");

        // Then: zero payments, but the day's refund total is carried
        assertEquals(0, response.getOrderCount());
        assertEquals(0, BigDecimal.ZERO.compareTo(response.getTotalPaymentAmount()));
        assertEquals(0, new BigDecimal("42.00").compareTo(response.getTotalRefundAmount()));
        // And the audit trail still records the batch generation
        verify(auditLogService).record(eq("999"), eq("SETTLEMENT_BATCH_GENERATE"),
                any(), any(), eq(SettlementStatus.GENERATED.name()), any());
    }

    // ---- helper ----

    private PaymentRecord createPayment(Long orderId, String paymentNo,
                                         BigDecimal paidAmount, PaymentStatus status) {
        PaymentRecord p = new PaymentRecord();
        p.setPaymentNo(paymentNo);
        p.setOrderId(orderId);
        p.setPaidAmount(paidAmount);
        p.setStatus(status);
        return p;
    }
}
