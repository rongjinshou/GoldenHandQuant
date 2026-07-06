package com.ecommerce.payment.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.payment.dto.InvoiceRequest;
import com.ecommerce.payment.dto.InvoiceResponse;
import com.ecommerce.payment.entity.InvoiceRecord;
import com.ecommerce.payment.entity.InvoiceStatus;
import com.ecommerce.payment.entity.InvoiceType;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.InvoiceRecordRepository;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link InvoiceService}.
 *
 * <p>Verifies invoice amount and tax calculations from invoice.tax-rate
 * config (default 0.06 = 6%). Per design-docs/09 §6 / design-docs/14 §3,
 * {@code generateInvoice()} must honor {@code request.getInvoiceAmount()}
 * (partial invoicing), and reject any request whose amount exceeds the
 * order's remaining invoiceable amount with {@code INVOICE_AMOUNT_EXCEEDED}.
 */
@ExtendWith(MockitoExtension.class)
class InvoiceServiceTest {

    @Mock
    private InvoiceRecordRepository invoiceRecordRepository;

    @Mock
    private PaymentRecordRepository paymentRecordRepository;

    private InvoiceService invoiceService;

    @BeforeEach
    void setUp() {
        invoiceService = new InvoiceService(invoiceRecordRepository, paymentRecordRepository);
    }

    // ---- generateInvoice_partialAmount_recordsRequestedAmountNotFullPaid ----

    @Test
    @DisplayName("generateInvoice respects request.invoiceAmount for partial invoicing")
    void generateInvoice_partialAmount_recordsRequestedAmountNotFullPaid() {
        // Given: request asks for only 30.00 invoice of a 100.00 order
        InvoiceRequest request = new InvoiceRequest(
                1L, InvoiceType.PERSONAL,
                new BigDecimal("30.00"),
                "Test Buyer", "TAX123"
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY001");
        payment.setOrderId(1L);
        payment.setPaidAmount(new BigDecimal("100.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(1L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                1L, InvoiceStatus.ISSUED)).thenReturn(BigDecimal.ZERO);
        when(invoiceRecordRepository.save(any(InvoiceRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        InvoiceResponse response = invoiceService.generateInvoice(100L, request);

        // Then: invoice amount is the requested 30.00, NOT the full 100.00 paid
        assertEquals(new BigDecimal("30.00"), response.getInvoiceAmount(),
                "invoiceAmount must reflect the requested amount, not the full paid amount");
        assertEquals(0, new BigDecimal("70.00").compareTo(response.getRemainingInvoiceableAmount()),
                "remaining = 100.00 paid - 30.00 invoiced = 70.00");
    }

    // ---- generateInvoice_amountExceedsRemaining_throwsInvoiceAmountExceeded ----

    @Test
    @DisplayName("generateInvoice rejects an amount exceeding the remaining invoiceable amount")
    void generateInvoice_amountExceedsRemaining_throwsInvoiceAmountExceeded() {
        // Given: order paid 100.00, already invoiced 80.00 -> only 20.00 remains
        InvoiceRequest request = new InvoiceRequest(
                5L, InvoiceType.PERSONAL,
                new BigDecimal("30.00"),
                "Test Buyer", "TAX999"
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY005");
        payment.setOrderId(5L);
        payment.setPaidAmount(new BigDecimal("100.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(5L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                5L, InvoiceStatus.ISSUED)).thenReturn(new BigDecimal("80.00"));

        // When/Then: requesting 30.00 when only 20.00 remains is rejected
        BusinessException ex = assertThrows(BusinessException.class,
                () -> invoiceService.generateInvoice(200L, request));
        assertEquals("INVOICE_AMOUNT_EXCEEDED", ex.getCode());
    }

    // ---- generateInvoice_duplicateInvoiceRequestNo_returnsExistingRecord_doesNotCreateSecond ----

    @Test
    @DisplayName("generateInvoice with a duplicate invoiceRequestNo returns the existing record")
    void generateInvoice_duplicateInvoiceRequestNo_returnsExistingRecord_doesNotCreateSecond() {
        InvoiceRequest request = new InvoiceRequest(
                6L, InvoiceType.PERSONAL,
                new BigDecimal("40.00"),
                "Test Buyer", "TAX111"
        );
        request.setInvoiceRequestNo("INV-REQ-001");

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY006");
        payment.setOrderId(6L);
        payment.setPaidAmount(new BigDecimal("100.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(6L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                6L, InvoiceStatus.ISSUED)).thenReturn(BigDecimal.ZERO);

        InvoiceRecord saved = new InvoiceRecord();
        when(invoiceRecordRepository.save(any(InvoiceRecord.class)))
                .thenAnswer(invocation -> {
                    InvoiceRecord arg = invocation.getArgument(0);
                    saved.setId(1L);
                    saved.setInvoiceNo(arg.getInvoiceNo());
                    saved.setInvoiceRequestNo(arg.getInvoiceRequestNo());
                    saved.setOrderId(arg.getOrderId());
                    saved.setInvoiceAmount(arg.getInvoiceAmount());
                    saved.setStatus(arg.getStatus());
                    return saved;
                });

        InvoiceResponse first = invoiceService.generateInvoice(100L, request);

        when(invoiceRecordRepository.findByInvoiceRequestNo("INV-REQ-001"))
                .thenReturn(java.util.Optional.of(saved));
        InvoiceResponse second = invoiceService.generateInvoice(100L, request);

        assertEquals(first.getInvoiceNo(), second.getInvoiceNo());
        verify(invoiceRecordRepository, times(1)).save(any(InvoiceRecord.class));
    }

    // ---- testGenerateInvoice_usesHardcodedTaxRate ----

    @Test
    @DisplayName("generateInvoice calculates tax amount")
    void testGenerateInvoice_usesHardcodedTaxRate() {
        // Given
        InvoiceRequest request = new InvoiceRequest(
                2L, InvoiceType.COMPANY,
                new BigDecimal("200.00"), // full amount requested (equals paid amount)
                "Company Ltd", "TAX456"
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY002");
        payment.setOrderId(2L);
        payment.setPaidAmount(new BigDecimal("200.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(2L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                2L, InvoiceStatus.ISSUED)).thenReturn(BigDecimal.ZERO);
        when(invoiceRecordRepository.save(any(InvoiceRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        InvoiceResponse response = invoiceService.generateInvoice(100L, request);

        // Then: default tax rate is 0.06 (6%)
        assertEquals(new BigDecimal("0.06"), response.getTaxRate(),
                "tax rate should default to 0.06");

        // Tax amount = 200 * 0.06 = 12.00
        assertEquals(new BigDecimal("12.00"), response.getTaxAmount(),
                "tax = 200.00 * 0.06 = 12.00");
    }

    // ---- testGenerateInvoice_singleInvoiceConsumesAll ----

    @Test
    @DisplayName("single invoice consumes all remaining invoiceable amount (remaining = 0)")
    void testGenerateInvoice_singleInvoiceConsumesAll() {
        // Given: single invoice for full order amount
        InvoiceRequest request = new InvoiceRequest(
                3L, InvoiceType.VAT_SPECIAL,
                new BigDecimal("500.00"),
                "VAT Company", "TAX789"
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY003");
        payment.setOrderId(3L);
        payment.setPaidAmount(new BigDecimal("500.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(3L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                3L, InvoiceStatus.ISSUED)).thenReturn(BigDecimal.ZERO);
        when(invoiceRecordRepository.save(any(InvoiceRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        InvoiceResponse response = invoiceService.generateInvoice(200L, request);

        // Then: remainingInvoiceableAmount = 0 after one full invoice
        assertTrue(BigDecimal.ZERO.compareTo(response.getRemainingInvoiceableAmount()) == 0,
                "After one full invoice, remaining invoiceable amount should be 0 (MonetaryUtil returns 0.00 with scale 2)");

        // Second invoice attempt should fail (already fully invoiced)
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                3L, InvoiceStatus.ISSUED)).thenReturn(new BigDecimal("500.00"));

        assertThrows(BusinessException.class,
                () -> invoiceService.generateInvoice(200L, request));
    }

    // ---- testCalculateTaxAmount_appliesHardcodedRate ----

    @Test
    @DisplayName("tax amount is calculated from invoice amount")
    void testCalculateTaxAmount_appliesHardcodedRate() {
        // Given: order with exact amount to verify tax calculation
        InvoiceRequest request = new InvoiceRequest(
                4L, InvoiceType.PERSONAL,
                new BigDecimal("150.00"),
                "Person", "TAX000"
        );

        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo("PAY004");
        payment.setOrderId(4L);
        payment.setPaidAmount(new BigDecimal("150.00"));
        payment.setStatus(PaymentStatus.SUCCESS);

        when(paymentRecordRepository.findByOrderId(4L))
                .thenReturn(Arrays.asList(payment));
        when(invoiceRecordRepository.sumInvoiceAmountByOrderIdAndStatus(
                4L, InvoiceStatus.ISSUED)).thenReturn(BigDecimal.ZERO);
        when(invoiceRecordRepository.save(any(InvoiceRecord.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        InvoiceResponse response = invoiceService.generateInvoice(300L, request);

        // Then: tax = 150.00 * 0.06 = 9.00
        assertEquals(new BigDecimal("9.00"), response.getTaxAmount(),
                "tax = 150.00 * 0.06 = 9.00");
    }
}
