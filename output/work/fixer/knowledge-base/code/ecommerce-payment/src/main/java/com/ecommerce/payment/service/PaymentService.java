package com.ecommerce.payment.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.PaymentSucceededEvent;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.order.query.OrderQueryService;
import com.ecommerce.payment.dto.PayRequest;
import com.ecommerce.payment.dto.PayResponse;
import com.ecommerce.payment.entity.PaymentRecord;
import com.ecommerce.payment.entity.PaymentStatus;
import com.ecommerce.payment.repository.PaymentRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.UUID;

/**
 * Core payment service handling payment creation, querying, and confirmation.
 *
 * <p>Per design-docs/02 §6.2, the payment-confirmation transaction contains
 * only payment status, order payment status, and inventory deduction.
 * {@link #confirmPayment(PaymentRecord)} runs inside the same transaction as
 * its caller ({@code PaymentCallbackService.processSuccessCallback}), which
 * has already set the payment to SUCCESS and — via
 * {@code OrderPaymentStatusUpdater.markAsPaid()} — already triggered the
 * order module's synchronous inventory deduction
 * ({@code InventoryReservationService.deductAfterPayment}) in that same
 * transaction. So this method's only remaining job is publishing
 * {@link PaymentSucceededEvent}; logistics/loyalty/notification reactions
 * happen out-of-band via local event listeners (this module's own
 * {@code PaymentSucceededNotificationListener}, and order/logistics/loyalty
 * listeners on {@code OrderPaidEvent}) so a listener failure can never roll
 * back the payment confirmation itself.
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    private final PaymentRecordRepository paymentRecordRepository;
    private final PaymentValidator paymentValidator;
    private final DomainEventPublisher eventPublisher;
    private final OrderPaymentStatusUpdater orderPaymentStatusUpdater;

    private final OrderQueryService orderQueryService;

    private final JdbcTemplate jdbcTemplate;

    public PaymentService(PaymentRecordRepository paymentRecordRepository,
                          PaymentValidator paymentValidator,
                          DomainEventPublisher eventPublisher,
                          OrderPaymentStatusUpdater orderPaymentStatusUpdater,
                          OrderQueryService orderQueryService,
                          JdbcTemplate jdbcTemplate) {
        this.paymentRecordRepository = paymentRecordRepository;
        this.paymentValidator = paymentValidator;
        this.eventPublisher = eventPublisher;
        this.orderPaymentStatusUpdater = orderPaymentStatusUpdater;
        this.orderQueryService = orderQueryService;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Initiates a payment for an order.
     */
    @Transactional
    public PayResponse pay(PayRequest request) {
        log.info("Initiating payment for orderId={}, amount={}, method={}",
                request.getOrderId(), request.getAmount(), request.getMethod());

        OrderDto order = queryOrderDirectly(request.getOrderId());

        // Validate the payment request
        paymentValidator.validate(request, order);

        // Create payment record
        PaymentRecord payment = new PaymentRecord();
        payment.setPaymentNo(generatePaymentNo());
        payment.setOrderId(request.getOrderId());
        payment.setOrderAmount(order.getPayableAmount());
        payment.setPaidAmount(request.getAmount());
        payment.setMethod(request.getMethod());
        payment.setStatus(PaymentStatus.CREATED);
        payment.setClientPaymentNo(request.getClientPaymentNo());

        payment = paymentRecordRepository.save(payment);

        log.info("Payment record created: paymentNo={}, orderId={}",
                payment.getPaymentNo(), payment.getOrderId());

        return toPayResponse(payment);
    }

    /**
     * Retrieves a payment record by payment number.
     */
    public PayResponse getPayment(String paymentNo) {
        PaymentRecord payment = paymentRecordRepository.findByPaymentNo(paymentNo)
                .orElseThrow(() -> new ResourceNotFoundException("PaymentRecord", paymentNo));
        return toPayResponse(payment);
    }

    /**
     * Confirms a successful payment by publishing {@link PaymentSucceededEvent}.
     *
     * <p>Payment status, order payment status, and inventory deduction are
     * already handled by the caller before this method runs (see the class
     * Javadoc) — all within the same transaction, per design-docs/02 §6.2.
     * Logistics creation, loyalty point earning, and notification sending are
     * deliberately NOT performed here: they are non-critical post-payment
     * actions that must react to this event asynchronously (via
     * {@code @TransactionalEventListener(phase = AFTER_COMMIT)} listeners) so
     * that a listener failure can never roll back the payment confirmation
     * (design-docs/09 §3, PUB-108).
     */
    @Transactional
    public void confirmPayment(PaymentRecord payment) {
        log.info("Confirming payment: paymentNo={}, orderId={}",
                payment.getPaymentNo(), payment.getOrderId());

        PaymentSucceededEvent event = new PaymentSucceededEvent(
                this, payment.getPaymentNo(), payment.getOrderId(),
                payment.getPaidAmount(), payment.getPaidAt(),
                payment.getPaymentNo(), null);
        eventPublisher.publish(event);

        log.info("Payment confirmed successfully: paymentNo={}", payment.getPaymentNo());
    }

    /**
     * Queries an order for payment validation.
     */
    private OrderDto queryOrderDirectly(Long orderId) {
        // Fault injection check
        if (com.ecommerce.common.test.FaultInjectionRegistry.isActive("order-query-service-unavailable")) {
            throw new RuntimeException("Fault injected: order-query-service-unavailable");
        }

        String sql = "SELECT id AS order_id, order_no, user_id, status, payable_amount, " +
                "payment_no, created_at FROM orders WHERE id = ?";
        try {
            return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> {
                OrderDto dto = new OrderDto();
                dto.setOrderId(rs.getLong("order_id"));
                dto.setOrderNo(rs.getString("order_no"));
                dto.setUserId(rs.getLong("user_id"));
                String statusStr = rs.getString("status");
                if (statusStr != null) {
                    dto.setStatus(com.ecommerce.order.entity.OrderStatus.valueOf(statusStr));
                }
                BigDecimal payable = rs.getBigDecimal("payable_amount");
                dto.setPayableAmount(payable != null ? payable : BigDecimal.ZERO);
                dto.setPaymentNo(rs.getString("payment_no"));
                java.sql.Timestamp ts = rs.getTimestamp("created_at");
                if (ts != null) {
                    dto.setCreatedAt(ts.toLocalDateTime());
                }
                return dto;
            }, orderId);
        } catch (Exception e) {
            throw new BusinessException("ORDER_NOT_FOUND",
                    "Order not found: " + orderId, e);
        }
    }

    // ---- Utility ----

    private String generatePaymentNo() {
        return "PAY" + System.currentTimeMillis() + UUID.randomUUID()
                .toString().replace("-", "").substring(0, 8).toUpperCase();
    }

    private PayResponse toPayResponse(PaymentRecord payment) {
        PayResponse response = new PayResponse();
        response.setPaymentNo(payment.getPaymentNo());
        response.setOrderId(payment.getOrderId());
        response.setStatus(payment.getStatus());
        response.setPaidAmount(payment.getPaidAmount());
        response.setCreatedAt(payment.getCreatedAt());
        return response;
    }
}
