package com.ecommerce.payment.service;

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
 * <p>Per design-docs/14 §5, a settlement batch includes only successfully
 * paid orders (not PENDING/FAILED attempts), and must reflect real refund
 * totals rather than a hardcoded zero.
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

    private SettlementBatchService settlementBatchService;

    @BeforeEach
    void setUp() {
        settlementBatchService = new SettlementBatchService(
                settlementBatchRepository,
                settlementOrderItemRepository,
                paymentRecordRepository,
                invoiceRecordRepository,
                refundRecordRepository
        );
    }

    // ---- testGenerateBatch_onlyIncludesSuccessPayments ----

    @Test
    @DisplayName("settlement only includes SUCCESS payments, not PENDING/FAILED")
    void testGenerateBatch_onlyIncludesSuccessPayments() {
        // Given: only the SUCCESS payments are returned by the
        // status-filtered repository query — PENDING/FAILED never reach the
        // service, matching design-docs/14 §5 ("支付成功且未结算的订单").
        LocalDate batchDate = LocalDate.of(2026, 6, 1);

        PaymentRecord paid1 = createPayment(1L, "PAY001", new BigDecimal("100.00"), PaymentStatus.SUCCESS);
        PaymentRecord paid2 = createPayment(2L, "PAY002", new BigDecimal("200.00"), PaymentStatus.SUCCESS);

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusAndPaidAtBetween(
                eq(PaymentStatus.SUCCESS), any(), any()))
                .thenReturn(Arrays.asList(paid1, paid2));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.COMPLETED), any(), any()))
                .thenReturn(Collections.emptyList());

        when(settlementBatchRepository.save(any(SettlementBatch.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate);

        // Then: only the 2 SUCCESS payments are included
        assertNotNull(response);
        assertEquals(2, response.getOrderCount(), "settlement order count");
        assertEquals(new BigDecimal("300.00"), response.getTotalPaymentAmount(),
                "total=300 from the 2 SUCCESS payments only");

        // And the unfiltered (status-agnostic) query is never used
        verify(paymentRecordRepository, never()).findByPaidAtBetween(any(), any());
    }

    // ---- testGenerateBatch_calculatesTotals ----

    @Test
    @DisplayName("settlement batch calculates totals from SUCCESS payments only")
    void testGenerateBatch_calculatesTotals() {
        // Given: only SUCCESS payments are returned (status filter applied at the query level)
        LocalDate batchDate = LocalDate.of(2026, 6, 2);

        PaymentRecord payment1 = createPayment(10L, "PAY010", new BigDecimal("150.00"), PaymentStatus.SUCCESS);
        PaymentRecord payment2 = createPayment(20L, "PAY020", new BigDecimal("350.00"), PaymentStatus.SUCCESS);

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusAndPaidAtBetween(
                eq(PaymentStatus.SUCCESS), any(), any()))
                .thenReturn(Arrays.asList(payment1, payment2));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.COMPLETED), any(), any()))
                .thenReturn(Collections.emptyList());

        ArgumentCaptor<SettlementBatch> batchCaptor =
                ArgumentCaptor.forClass(SettlementBatch.class);
        when(settlementBatchRepository.save(batchCaptor.capture()))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate);

        // Then: totals include only the 2 SUCCESS payments
        assertEquals(2, response.getOrderCount(), "2 SUCCESS orders");
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
        // Given: one SUCCESS payment and one COMPLETED refund of 30.00 on the batch date
        LocalDate batchDate = LocalDate.of(2026, 6, 3);

        PaymentRecord payment = createPayment(40L, "PAY040", new BigDecimal("100.00"), PaymentStatus.SUCCESS);

        RefundRecord refund = new RefundRecord();
        refund.setRefundNo("RF040");
        refund.setPaymentNo("PAY040");
        refund.setOrderId(40L);
        refund.setUserId(1L);
        refund.setRefundAmount(new BigDecimal("30.00"));
        refund.setStatus(RefundStatus.COMPLETED);
        refund.setCompletedAt(batchDate.atTime(10, 0));

        when(settlementBatchRepository.findByBatchDate(batchDate))
                .thenReturn(Optional.empty());
        when(paymentRecordRepository.findByStatusAndPaidAtBetween(
                eq(PaymentStatus.SUCCESS), any(), any()))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.findAll()).thenReturn(Collections.emptyList());
        when(refundRecordRepository.findByStatusAndCompletedAtBetween(
                eq(RefundStatus.COMPLETED), any(), any()))
                .thenReturn(Arrays.asList(refund));

        when(settlementBatchRepository.save(any(SettlementBatch.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(settlementOrderItemRepository.save(any()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        SettlementBatchResponse response = settlementBatchService.generateBatch(batchDate);

        // Then: the real refund total (30.00) is reflected, not a hardcoded zero
        assertEquals(0, new BigDecimal("30.00").compareTo(response.getTotalRefundAmount()));
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
