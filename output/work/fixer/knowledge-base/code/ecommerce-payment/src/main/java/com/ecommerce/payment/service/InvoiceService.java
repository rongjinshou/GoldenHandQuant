package com.ecommerce.payment.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.exception.ValidationException;
import com.ecommerce.common.money.MonetaryUtil;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.payment.dto.InvoiceRequest;
import com.ecommerce.payment.dto.InvoiceResponse;
import com.ecommerce.payment.entity.InvoiceRecord;
import com.ecommerce.payment.entity.InvoiceStatus;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.InvoiceRecordRepository;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Handles invoice generation for paid orders.
 */
@Service
public class InvoiceService {

    private static final Logger log = LoggerFactory.getLogger(InvoiceService.class);

    // Fallback only: RuntimeConfigRegistry's own hardcoded defaults already
    // resolve "invoice.tax-rate" to 0.06 (design-docs/09 §6, design-docs/附录B),
    // so this constant is only ever used if that lookup mechanism changes.
    private static final BigDecimal TAX_RATE = new BigDecimal("0.06");

    private final InvoiceRecordRepository invoiceRecordRepository;
    private final PaymentRecordRepository paymentRecordRepository;

    public InvoiceService(InvoiceRecordRepository invoiceRecordRepository,
                          PaymentRecordRepository paymentRecordRepository) {
        this.invoiceRecordRepository = invoiceRecordRepository;
        this.paymentRecordRepository = paymentRecordRepository;
    }

    /**
     * Generates an invoice for an order.
     */
    @Transactional
    public InvoiceResponse generateInvoice(Long userId, InvoiceRequest request) {
        log.info("Generating invoice: userId={}, orderId={}, type={}, requestedAmount={}",
                userId, request.getOrderId(), request.getInvoiceType(), request.getInvoiceAmount());

        // Idempotency: a repeated invoiceRequestNo returns the existing record
        // instead of creating a duplicate invoice (design-docs/03 §3).
        if (request.getInvoiceRequestNo() != null) {
            Optional<InvoiceRecord> existing = invoiceRecordRepository
                    .findByInvoiceRequestNo(request.getInvoiceRequestNo());
            if (existing.isPresent()) {
                log.info("Duplicate invoice request ignored: invoiceRequestNo={}",
                        request.getInvoiceRequestNo());
                return toInvoiceResponse(existing.get());
            }
        }

        if (request.getInvoiceAmount() == null
                || request.getInvoiceAmount().compareTo(BigDecimal.ZERO) <= 0) {
            throw new ValidationException("invoiceAmount",
                    "Invoice amount must be greater than 0");
        }

        // Find the successful payment for this order
        List<PaymentRecord> payments = paymentRecordRepository.findByOrderId(request.getOrderId());
        PaymentRecord successfulPayment = payments.stream()
                .filter(p -> p.getStatus() == PaymentStatus.SUCCESS)
                .findFirst()
                .orElseThrow(() -> new BusinessException("NO_PAID_PAYMENT",
                        "Order " + request.getOrderId() + " has no successful payment"));

        // Invoice amount comes from the request — partial invoicing is allowed
        // (design-docs/09 §6, design-docs/14 §3).
        BigDecimal invoiceAmount = request.getInvoiceAmount();

        // Check remaining invoiceable amount: single-invoice amount must not
        // exceed what's left (design-docs/14 §3: remaining = paidAmount - alreadyInvoiced).
        BigDecimal alreadyInvoiced = invoiceRecordRepository
                .sumInvoiceAmountByOrderIdAndStatus(request.getOrderId(), InvoiceStatus.ISSUED);
        BigDecimal remaining = MonetaryUtil.subtract(
                successfulPayment.getPaidAmount(), alreadyInvoiced);

        if (invoiceAmount.compareTo(remaining) > 0) {
            throw new BusinessException("INVOICE_AMOUNT_EXCEEDED",
                    "Requested invoice amount " + invoiceAmount
                            + " exceeds remaining invoiceable amount " + remaining);
        }

        BigDecimal taxRate = RuntimeConfigRegistry.getBigDecimal("invoice.tax-rate", TAX_RATE);
        BigDecimal taxAmount = MonetaryUtil.roundToCent(
                invoiceAmount.multiply(taxRate).setScale(4, RoundingMode.HALF_UP));

        // Compute new remaining after this invoice
        BigDecimal newRemaining = MonetaryUtil.subtract(remaining, invoiceAmount);

        InvoiceRecord invoice = new InvoiceRecord();
        invoice.setInvoiceNo(generateInvoiceNo());
        invoice.setOrderId(request.getOrderId());
        invoice.setUserId(userId);
        invoice.setInvoiceType(request.getInvoiceType());
        invoice.setInvoiceAmount(invoiceAmount);
        invoice.setTaxRate(taxRate);
        invoice.setTaxAmount(taxAmount);
        invoice.setRemainingInvoiceableAmount(newRemaining);
        invoice.setInvoiceTitle(request.getInvoiceTitle());
        invoice.setTaxId(request.getTaxId());
        invoice.setStatus(InvoiceStatus.ISSUED);
        invoice.setIssuedAt(LocalDateTime.now());
        invoice.setInvoiceRequestNo(request.getInvoiceRequestNo());

        invoice = invoiceRecordRepository.save(invoice);

        log.info("Invoice generated: invoiceNo={}, amount={}, taxAmount={}, remaining={}",
                invoice.getInvoiceNo(), invoice.getInvoiceAmount(), invoice.getTaxAmount(),
                invoice.getRemainingInvoiceableAmount());

        return toInvoiceResponse(invoice);
    }

    /**
     * Gets all invoices for an order.
     */
    public List<InvoiceResponse> getInvoicesByOrderId(Long orderId) {
        List<InvoiceRecord> invoices = invoiceRecordRepository.findByOrderId(orderId);
        return invoices.stream()
                .map(this::toInvoiceResponse)
                .collect(Collectors.toList());
    }

    private String generateInvoiceNo() {
        return "INV" + System.currentTimeMillis() + UUID.randomUUID()
                .toString().replace("-", "").substring(0, 8).toUpperCase();
    }

    private InvoiceResponse toInvoiceResponse(InvoiceRecord invoice) {
        InvoiceResponse response = new InvoiceResponse();
        response.setId(invoice.getId());
        response.setInvoiceNo(invoice.getInvoiceNo());
        response.setOrderId(invoice.getOrderId());
        response.setUserId(invoice.getUserId());
        response.setInvoiceType(invoice.getInvoiceType());
        response.setInvoiceAmount(invoice.getInvoiceAmount());
        response.setTaxRate(invoice.getTaxRate());
        response.setTaxAmount(invoice.getTaxAmount());
        response.setRemainingInvoiceableAmount(invoice.getRemainingInvoiceableAmount());
        response.setInvoiceTitle(invoice.getInvoiceTitle());
        response.setTaxId(invoice.getTaxId());
        response.setStatus(invoice.getStatus());
        response.setIssuedAt(invoice.getIssuedAt());
        response.setCreatedAt(invoice.getCreatedAt());
        return response;
    }
}
