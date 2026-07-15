package com.ecommerce.payment.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.money.MonetaryUtil;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.payment.dto.PaymentCallbackRequest;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;

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

        // CLOSED is terminal (the payment was refunded and closed, 附录C
        // payments.status) — a SUCCESS callback must not resurrect it. Same
        // state-conflict semantics (409) as FAILED-after-SUCCESS below.
        if (payment.getStatus() == PaymentStatus.CLOSED) {
            throw new ConflictException("PAYMENT_STATUS_CONFLICT",
                    "Cannot mark as SUCCESS when payment is already CLOSED");
        }

        // design-docs/09 §2: the paid amount must equal the order's payable amount,
        // which was locked onto this payment record at pay() time. The callback is
        // where the payment is marked SUCCESS and its paidAmount becomes the basis
        // for later refunds/invoices, so a mismatched callback amount must be
        // rejected here rather than trusted — mirroring PaymentValidator at pay().
        BigDecimal callbackAmount = MonetaryUtil.roundToCent(request.getAmount());
        if (payment.getOrderAmount() == null
                || callbackAmount.compareTo(payment.getOrderAmount()) != 0) {
            throw new BusinessException("PAYMENT_AMOUNT_MISMATCH",
                    "Callback amount " + callbackAmount
                            + " does not match order payable amount " + payment.getOrderAmount());
        }

        payment.setStatus(PaymentStatus.SUCCESS);
        payment.setPaidAmount(callbackAmount);
        // Business timestamps use the test-support system clock so admin
        // clock-shift scenarios observe consistent payment times (equal to the
        // real system time whenever the clock is not shifted).
        payment.setPaidAt(SystemClockService.now());
        payment.setCallbackSequence(request.getCallbackSequence());
        payment.setCallbackData("Callback processed at " + SystemClockService.now());
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

        // CLOSED is terminal (refunded) — a stray/late FAILED callback is
        // short-circuited as a no-op and must never flip CLOSED to FAILED.
        if (payment.getStatus() == PaymentStatus.CLOSED) {
            log.info("Payment already CLOSED, ignoring FAILED callback: paymentNo={}",
                    request.getPaymentNo());
            return;
        }

        if (payment.getStatus() == PaymentStatus.SUCCESS) {
            throw new ConflictException("PAYMENT_STATUS_CONFLICT",
                    "Cannot mark as FAILED when already SUCCESS");
        }

        payment.setStatus(PaymentStatus.FAILED);
        payment.setCallbackSequence(request.getCallbackSequence());
        payment.setCallbackData("Failed callback at " + SystemClockService.now());
        paymentRecordRepository.save(payment);

        // Update order payment status
        orderPaymentStatusUpdater.markPaymentFailed(payment.getOrderId());

        log.info("Payment callback failed: paymentNo={}", request.getPaymentNo());
    }
}
