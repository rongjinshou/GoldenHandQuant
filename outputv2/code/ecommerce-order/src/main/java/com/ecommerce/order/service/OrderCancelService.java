package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.inventory.query.InventoryReservationService;
import com.ecommerce.loyalty.query.LoyaltyCommandService;
import com.ecommerce.order.dto.CancelOrderResponse;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.event.OrderCancelledEvent;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.promotion.service.CouponService;
import com.ecommerce.promotion.service.SeckillService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Handles order cancellation with different logic per order status.
 *
 * <p>Cancellation rules:
 * <ul>
 *   <li>CREATED: Direct cancel, release inventory</li>
 *   <li>PAYING: User can cancel, payment callback handles idempotency</li>
 *   <li>PAID: Cancel with refund handling</li>
 *   <li>SHIPPED: Cannot cancel, must use after-sale return</li>
 *   <li>DELIVERED: Cannot cancel, must use return/refund</li>
 * </ul>
 */
@Service
public class OrderCancelService {

    private static final Logger log = LoggerFactory.getLogger(OrderCancelService.class);

    private final OrderRepository orderRepository;
    private final InventoryReservationService inventoryReservationService;
    private final OrderStateMachine stateMachine;
    private final DomainEventPublisher eventPublisher;
    private final OrderService orderService;
    private final CouponService couponService;
    private final SeckillService seckillService;
    private final LoyaltyCommandService loyaltyCommandService;

    public OrderCancelService(OrderRepository orderRepository,
                              InventoryReservationService inventoryReservationService,
                              OrderStateMachine stateMachine,
                              DomainEventPublisher eventPublisher,
                              OrderService orderService,
                              CouponService couponService,
                              SeckillService seckillService,
                              LoyaltyCommandService loyaltyCommandService) {
        this.orderRepository = orderRepository;
        this.inventoryReservationService = inventoryReservationService;
        this.stateMachine = stateMachine;
        this.eventPublisher = eventPublisher;
        this.orderService = orderService;
        this.couponService = couponService;
        this.seckillService = seckillService;
        this.loyaltyCommandService = loyaltyCommandService;
    }

    /**
     * Cancel an order by user request.
     *
     * @param userId  the user ID requesting the cancellation
     * @param orderId the order ID to cancel
     * @param reason  cancellation reason
     * @return the cancel response
     */
    @Transactional
    public CancelOrderResponse cancel(Long userId, Long orderId, String reason) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        // Verify ownership
        if (!order.getUserId().equals(userId)) {
            throw new BusinessException("ORDER_NOT_OWNED",
                    "Order " + orderId + " does not belong to user " + userId);
        }

        OrderStatus currentStatus = order.getStatus();

        switch (currentStatus) {
            case CREATED:
                return cancelCreatedOrder(order, reason);

            case PAYING:
                return cancelPayingOrder(order, reason);

            case PAID:
                return requestPaidOrderCancelReview(order, reason);

            case SHIPPED:
            case DELIVERED:
                throw new ConflictException("ORDER_STATUS_CONFLICT",
                        "Order in status " + currentStatus + " cannot be cancelled. "
                                + "Please use the after-sale/return process.");

            case CANCELLED:
            case CLOSED:
                throw new ConflictException("ORDER_STATUS_CONFLICT",
                        "Order is already in status " + currentStatus);

            case CANCEL_REVIEWING:
                throw new ConflictException("ORDER_STATUS_CONFLICT",
                        "Order cancellation is already under review");

            default:
                throw new ConflictException("ORDER_STATUS_CONFLICT",
                        "Order in status " + currentStatus + " cannot be cancelled");
        }
    }

    /**
     * Cancel a CREATED order: direct cancel with inventory release.
     */
    private CancelOrderResponse cancelCreatedOrder(Order order, String reason) {
        OrderStatus fromStatus = order.getStatus();
        stateMachine.validateTransition(fromStatus, OrderStatus.CANCELLED);

        order.setStatus(OrderStatus.CANCELLED);
        order.setCancelReason(reason);
        order.setCancelledAt(SystemClockService.now());
        orderRepository.save(order);

        // Release reserved inventory
        try {
            inventoryReservationService.release(order.getId());
            log.info("Inventory released for cancelled order {}", order.getId());
        } catch (Exception e) {
            log.error("Failed to release inventory for order {}: {}", order.getId(), e.getMessage());
        }

        // Give back coupons and seckill allocation consumed by this order
        releasePromotions(order.getId());

        // Give back the loyalty points redeemed by this order
        refundLoyaltyPoints(order.getId());

        // Record event
        orderService.recordEvent(order.getId(), fromStatus, OrderStatus.CANCELLED,
                "CANCEL", order.getUserId().toString(), "User cancelled: " + reason);

        // Publish event
        eventPublisher.publish(new OrderCancelledEvent(this, order.getId(), order.getUserId()));

        log.info("Order {} cancelled by user {}", order.getId(), order.getUserId());
        return new CancelOrderResponse(order.getId(), OrderStatus.CANCELLED.name(),
                "Order cancelled, inventory released");
    }

    /**
     * Cancel a PAYING order: mark as cancelled. Payment callback will handle
     * idempotency if payment was already in progress.
     */
    private CancelOrderResponse cancelPayingOrder(Order order, String reason) {
        OrderStatus fromStatus = order.getStatus();
        stateMachine.validateTransition(fromStatus, OrderStatus.CANCELLED);

        order.setStatus(OrderStatus.CANCELLED);
        order.setCancelReason(reason);
        order.setCancelledAt(SystemClockService.now());
        orderRepository.save(order);

        // Give back coupons and seckill allocation consumed by this order
        releasePromotions(order.getId());

        // Give back the loyalty points redeemed by this order
        refundLoyaltyPoints(order.getId());

        orderService.recordEvent(order.getId(), fromStatus, OrderStatus.CANCELLED,
                "CANCEL", order.getUserId().toString(),
                "User cancelled during payment: " + reason);

        eventPublisher.publish(new OrderCancelledEvent(this, order.getId(), order.getUserId()));

        log.info("PAYING order {} cancelled by user {}", order.getId(), order.getUserId());
        return new CancelOrderResponse(order.getId(), OrderStatus.CANCELLED.name(),
                "Order cancelled. If payment was processed, a refund will be issued.");
    }

    /**
     * Request cancellation of a PAID order: this does NOT cancel the order
     * directly. Per design-docs/08 §6, a paid order must first enter merchant
     * cancel review (CANCEL_REVIEWING); only after the review is approved
     * (see {@link #reviewCancel}) does it actually move to CANCELLED and
     * enter the refund process. Order service does not compute or apply any
     * refund amount itself — that belongs to the payment module's refund flow.
     */
    private CancelOrderResponse requestPaidOrderCancelReview(Order order, String reason) {
        OrderStatus fromStatus = order.getStatus();

        stateMachine.validateTransition(fromStatus, OrderStatus.CANCEL_REVIEWING);

        order.setStatus(OrderStatus.CANCEL_REVIEWING);
        order.setCancelReason(reason);
        orderRepository.save(order);

        orderService.recordEvent(order.getId(), fromStatus, OrderStatus.CANCEL_REVIEWING,
                "CANCEL_REQUESTED", order.getUserId().toString(),
                "User requested cancellation of paid order, pending merchant review: " + reason);

        log.info("PAID order {} cancellation requested by user {}, pending merchant review",
                order.getId(), order.getUserId());

        return new CancelOrderResponse(order.getId(), OrderStatus.CANCEL_REVIEWING.name(),
                "Cancellation request submitted for merchant review");
    }

    /**
     * Cancellation review flow.
     * Admin uses this via AdminOrderController.
     */
    @Transactional
    public CancelOrderResponse reviewCancel(Long orderId, boolean approved, String comment,
                                            Long reviewerId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        if (order.getStatus() != OrderStatus.CANCEL_REVIEWING) {
            throw new ConflictException("ORDER_STATUS_CONFLICT",
                    "Order " + orderId + " is not in CANCEL_REVIEWING status");
        }

        OrderStatus fromStatus = order.getStatus();

        if (approved) {
            // Approve cancellation: move to CANCELLED, initiate refund
            stateMachine.validateTransition(fromStatus, OrderStatus.CANCELLED);
            order.setStatus(OrderStatus.CANCELLED);
            order.setCancelReviewerId(reviewerId);
            order.setCancelledAt(SystemClockService.now());
            orderRepository.save(order);

            // Release inventory if still reserved
            try {
                inventoryReservationService.release(orderId);
            } catch (Exception e) {
                log.warn("Failed to release inventory during cancel review: {}", e.getMessage());
            }

            // Give back coupons and seckill allocation consumed by this order
            releasePromotions(orderId);

            // Give back the loyalty points redeemed by this order
            refundLoyaltyPoints(orderId);

            orderService.recordEvent(orderId, fromStatus, OrderStatus.CANCELLED,
                    "CANCEL_APPROVED", reviewerId.toString(),
                    "Admin approved cancellation: " + comment);

            return new CancelOrderResponse(orderId, OrderStatus.CANCELLED.name(),
                    "Cancellation approved, refund will be processed");
        } else {
            // Reject cancellation: revert to PAID
            stateMachine.validateTransition(fromStatus, OrderStatus.PAID);
            order.setStatus(OrderStatus.PAID);
            order.setCancelReason(null);
            orderRepository.save(order);

            orderService.recordEvent(orderId, fromStatus, OrderStatus.PAID,
                    "CANCEL_REJECTED", reviewerId.toString(),
                    "Admin rejected cancellation: " + comment);

            return new CancelOrderResponse(orderId, OrderStatus.PAID.name(),
                    "Cancellation rejected, order remains active");
        }
    }

    /**
     * Give back the coupons and the seckill allocation consumed by an order
     * once its cancellation has succeeded (mirrors the consumption side,
     * {@code OrderService} Step 10b). Both calls are best-effort: a release
     * failure is logged and swallowed — it must never block the cancellation
     * itself (design-docs/03: post-actions must not fail the main flow),
     * exactly like the inventory release above. Only invoked on paths that
     * actually reach CANCELLED — a PAID order entering CANCEL_REVIEWING keeps
     * its coupons/allocation until the review is approved.
     */
    private void releasePromotions(Long orderId) {
        try {
            couponService.releaseForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to release coupons for cancelled order {}: {}", orderId, e.getMessage());
        }
        try {
            seckillService.releaseForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to release seckill allocation for cancelled order {}: {}",
                    orderId, e.getMessage());
        }
    }

    /**
     * Give back the loyalty points a cancelled order had redeemed at creation
     * time (mirrors the consumption side, {@code OrderService} Step 10b).
     * Same best-effort contract as {@link #releasePromotions}: the refund is
     * idempotent on the loyalty side and a failure is logged and swallowed —
     * it must never block the cancellation itself. Only invoked on paths that
     * actually reach CANCELLED — a PAID order entering CANCEL_REVIEWING keeps
     * its points deduction until the review is approved.
     */
    private void refundLoyaltyPoints(Long orderId) {
        try {
            loyaltyCommandService.refundPointsForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to refund redeemed points for cancelled order {}: {}",
                    orderId, e.getMessage());
        }
    }
}
