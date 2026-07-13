package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.inventory.query.InventoryReservationService;
import com.ecommerce.loyalty.query.LoyaltyCommandService;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.event.OrderCancelledEvent;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.promotion.service.CouponService;
import com.ecommerce.promotion.service.SeckillService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Scheduled service that scans for and cancels expired orders.
 * Runs every 60 seconds to find CREATED orders past their expiresAt time.
 */
@Service
public class OrderTimeoutService {

    private static final Logger log = LoggerFactory.getLogger(OrderTimeoutService.class);

    private final OrderRepository orderRepository;
    private final DomainEventPublisher eventPublisher;
    private final OrderService orderService;
    private final InventoryReservationService inventoryReservationService;
    private final CouponService couponService;
    private final SeckillService seckillService;
    private final LoyaltyCommandService loyaltyCommandService;

    public OrderTimeoutService(OrderRepository orderRepository,
                                DomainEventPublisher eventPublisher,
                                OrderService orderService,
                                InventoryReservationService inventoryReservationService,
                                CouponService couponService,
                                SeckillService seckillService,
                                LoyaltyCommandService loyaltyCommandService) {
        this.orderRepository = orderRepository;
        this.eventPublisher = eventPublisher;
        this.orderService = orderService;
        this.inventoryReservationService = inventoryReservationService;
        this.couponService = couponService;
        this.seckillService = seckillService;
        this.loyaltyCommandService = loyaltyCommandService;
    }

    /**
     * Scan for and cancel expired orders.
     * Scheduled to run every 60 seconds with an initial delay of 30 seconds.
     */
    @Scheduled(fixedDelay = 60000, initialDelay = 30000)
    public void cancelExpiredOrders() {
        LocalDateTime now = SystemClockService.now();
        List<Order> expiredOrders = orderRepository
                .findByStatusAndExpiresAtBefore(OrderStatus.CREATED, now);

        if (expiredOrders.isEmpty()) {
            log.debug("No expired orders found at {}", now);
            return;
        }

        log.info("Found {} expired orders to cancel", expiredOrders.size());

        for (Order order : expiredOrders) {
            try {
                cancelExpiredOrder(order);
            } catch (Exception e) {
                log.error("Failed to cancel expired order {}: {}", order.getId(), e.getMessage(), e);
            }
        }
    }

    /**
     * Cancel a single expired order.
     * Package-private (rather than private) so it can be unit tested directly.
     *
     * @param order the expired order to cancel
     */
    void cancelExpiredOrder(Order order) {
        OrderStatus fromStatus = order.getStatus();

        order.setStatus(OrderStatus.CANCELLED);
        order.setCancelReason("Order expired — no payment received within 60 minutes");
        order.setCancelledAt(SystemClockService.now());
        orderRepository.save(order);

        // Release reserved inventory — an expired, never-paid order must not
        // hold onto stock indefinitely.
        inventoryReservationService.release(order.getId());

        // Give back coupons and seckill allocation consumed by this order —
        // a timeout cancellation returns the order's resources exactly like a
        // user-requested cancellation (OrderCancelService) does.
        releasePromotions(order.getId());

        // Give back the loyalty points redeemed by this order
        refundLoyaltyPoints(order.getId());

        // Record event
        orderService.recordEvent(order.getId(), fromStatus, OrderStatus.CANCELLED,
                "TIMEOUT_CANCEL", "SYSTEM",
                "Order expired at " + order.getExpiresAt());

        // Publish event
        eventPublisher.publish(new OrderCancelledEvent(this, order.getId(), order.getUserId()));

        log.warn("Expired order {} cancelled by timeout task.", order.getId());
    }

    /**
     * Give back the coupons and the seckill allocation consumed by an expired
     * order once its timeout cancellation has succeeded (mirrors the
     * consumption side, {@code OrderService} Step 10b, and the same helper in
     * {@code OrderCancelService}). Both calls are best-effort: a release
     * failure is logged and swallowed — it must never block the cancellation
     * itself (design-docs/03: post-actions must not fail the main flow).
     */
    private void releasePromotions(Long orderId) {
        try {
            couponService.releaseForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to release coupons for expired order {}: {}", orderId, e.getMessage());
        }
        try {
            seckillService.releaseForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to release seckill allocation for expired order {}: {}",
                    orderId, e.getMessage());
        }
    }

    /**
     * Give back the loyalty points an expired order had redeemed at creation
     * time. Same best-effort contract as {@link #releasePromotions}: the
     * refund is idempotent on the loyalty side and a failure is logged and
     * swallowed — it must never block the timeout cancellation itself.
     */
    private void refundLoyaltyPoints(Long orderId) {
        try {
            loyaltyCommandService.refundPointsForOrder(orderId);
        } catch (Exception e) {
            log.warn("Failed to refund redeemed points for expired order {}: {}",
                    orderId, e.getMessage());
        }
    }
}
