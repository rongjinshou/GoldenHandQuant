package com.ecommerce.payment.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.payment.dto.PaymentCallbackRequest;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * Handles payment gateway callback processing.
 */
@Service
public class PaymentCallbackService {

    private static final Logger log = LoggerFactory.getLogger(PaymentCallbackService.class);

    /**
     * Mock signature accepted for payment callbacks in this environment (no real
     * payment gateway exists to sign requests). Mirrors the black-box test
     * harness's {@code PaymentFixture#callback}, which always sends this
     * literal value via the {@code X-Payment-Signature} header — the same
     * convention already used by the logistics module's callback signature.
     */
    private static final String VALID_SIGNATURE = "valid-signature";

    private final PaymentRecordRepository paymentRecordRepository;
    private final OrderPaymentStatusUpdater orderPaymentStatusUpdater;
    private final PaymentService paymentService;

    public PaymentCallbackService(PaymentRecordRepository paymentRecordRepository,
                                  OrderPaymentStatusUpdater orderPaymentStatusUpdater,
                                  PaymentService paymentService) {
        this.paymentRecordRepository = paymentRecordRepository;
        this.orderPaymentStatusUpdater = orderPaymentStatusUpdater;
        this.paymentService = paymentService;
    }

    /**
     * Processes a payment callback from the payment gateway.
     *
     * @param request   the callback payload
     * @param signature value of the {@code X-Payment-Signature} header
     */
    @Transactional
    public void processCallback(PaymentCallbackRequest request, String signature) {
        log.info("Processing payment callback: paymentNo={}, status={}",
                request.getPaymentNo(), request.getStatus());

        // design-docs/02 §8.4 / 09 §3: the callback is authenticated via a
        // simulated signature header, verified before anything else.
        if (!VALID_SIGNATURE.equals(signature)) {
            throw AuthorizationException.unauthorized("Invalid payment callback signature");
        }

        // Idempotency check: if same callback sequence already processed
        if (request.getCallbackSequence() != null) {
            PaymentRecord existing = paymentRecordRepository
                    .findByPaymentNo(request.getPaymentNo())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "PaymentRecord", request.getPaymentNo()));
            if (request.getCallbackSequence().equals(existing.getCallbackSequence())) {
                log.info("Duplicate callback ignored: paymentNo={}, sequence={}",
                        request.getPaymentNo(), request.getCallbackSequence());
                return;
            }
        }

        if ("SUCCESS".equals(request.getStatus())) {
            processSuccessCallback(request);
        } else if ("FAILED".equals(request.getStatus())) {
            processFailedCallback(request);
        } else {
            log.warn("Unknown callback status: {}", request.getStatus());
        }
    }

    private void processSuccessCallback(PaymentCallbackRequest request) {
        PaymentRecord payment = paymentRecordRepository
                .findByPaymentNo(request.getPaymentNo())
                .orElseThrow(() -> new ResourceNotFoundException(
                        "PaymentRecord", request.getPaymentNo()));

        if (payment.getStatus() == PaymentStatus.SUCCESS) {
            log.info("Payment already SUCCESS: paymentNo={}", request.getPaymentNo());
            return;
        }

        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setPaidAmount(request.getAmount());
        payment.setPaidAt(LocalDateTime.now());
        payment.setCallbackSequence(request.getCallbackSequence());
        payment.setCallbackData("Callback processed at " + LocalDateTime.now());
        paymentRecordRepository.save(payment);

        // Update order payment status (also triggers, in the same transaction,
        // the order module's synchronous post-payment inventory deduction)
        orderPaymentStatusUpdater.markAsPaid(payment.getOrderId(), payment.getPaymentNo());

        // Confirm payment — publishes PaymentSucceededEvent for async listeners
        paymentService.confirmPayment(payment);

        log.info("Payment callback processed successfully: paymentNo={}", request.getPaymentNo());
    }

    private void processFailedCallback(PaymentCallbackRequest request) {
        PaymentRecord payment = paymentRecordRepository
                .findByPaymentNo(request.getPaymentNo())
                .orElseThrow(() -> new ResourceNotFoundException(
                        "PaymentRecord", request.getPaymentNo()));

        if (payment.getStatus() == PaymentStatus.FAILED) {
            log.info("Payment already FAILED, ignoring duplicate callback: paymentNo={}",
                    request.getPaymentNo());
            return;
        }

        if (payment.getStatus() == PaymentStatus.SUCCESS) {
            throw new BusinessException("PAYMENT_STATUS_CONFLICT",
                    "Cannot mark as FAILED when already SUCCESS");
        }

        payment.setStatus(PaymentStatus.FAILED);
        payment.setCallbackSequence(request.getCallbackSequence());
        payment.setCallbackData("Failed callback at " + LocalDateTime.now());
        paymentRecordRepository.save(payment);

        // Update order payment status
        orderPaymentStatusUpdater.markPaymentFailed(payment.getOrderId());

        log.info("Payment callback failed: paymentNo={}", request.getPaymentNo());
    }
}
