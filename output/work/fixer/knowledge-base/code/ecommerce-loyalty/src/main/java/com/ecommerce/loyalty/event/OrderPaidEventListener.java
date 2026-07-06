package com.ecommerce.loyalty.event;

import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.loyalty.service.LoyaltyPointService;
import com.ecommerce.loyalty.service.MemberLevelService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * Listens for {@link OrderPaidEvent} and awards loyalty points for the order.
 *
 * <p>This is the {@code com.ecommerce.common.event.OrderPaidEvent} published
 * by ecommerce-order after payment confirmation (design-docs/附录D §2).
 * loyalty previously defined and listened to its own module-local shadow of
 * this event, so Spring never routed the real, order-published event here
 * and order-payment points were never actually awarded; that shadow class
 * has been removed and this listener now depends on the shared common type.
 *
 * <p>On order paid:
 * <ol>
 *   <li>Refresh the user's member level against their up-to-date annual
 *       consumption <em>before</em> scoring (design-docs/12 §6.9 item 11),
 *       so this very payment's tier-multiplier reflects any tier crossed by
 *       this same payment.</li>
 *   <li>Calculate points via {@link LoyaltyPointService#calcOrderPoints}</li>
 *   <li>Award points via {@link LoyaltyPointService#earnPoints}</li>
 * </ol>
 *
 * <p>Bean name is qualified with the module ({@code loyaltyOrderPaidEventListener})
 * because ecommerce-logistics also registers a component simple-named
 * {@code OrderPaidEventListener}; both are distinct, per-module reactions to the
 * same event and must both be registered, so an explicit name avoids the
 * {@code ConflictingBeanDefinitionException} that a shared default name would cause.
 */
@Component("loyaltyOrderPaidEventListener")
public class OrderPaidEventListener {

    private static final Logger log = LoggerFactory.getLogger(OrderPaidEventListener.class);

    private final LoyaltyPointService loyaltyPointService;
    private final MemberLevelService memberLevelService;

    public OrderPaidEventListener(LoyaltyPointService loyaltyPointService,
                                   MemberLevelService memberLevelService) {
        this.loyaltyPointService = loyaltyPointService;
        this.memberLevelService = memberLevelService;
    }

    @EventListener
    public void onOrderPaid(OrderPaidEvent event) {
        log.info("Received OrderPaidEvent: orderId={}, userId={}, amount={}",
                event.getOrderId(), event.getUserId(), event.getPaidAmount());

        try {
            // Track this payment against the user's running annual
            // consumption and re-evaluate their member level before scoring,
            // so calcOrderPoints below uses the correct, current multiplier.
            memberLevelService.recordPaymentAndEvaluate(event.getUserId(), event.getPaidAmount());

            int points = loyaltyPointService.calcOrderPoints(
                    event.getPaidAmount(), event.getUserId(), 1.0);
            if (points > 0) {
                loyaltyPointService.earnPoints(
                        event.getUserId(), points, "ORDER",
                        event.getOrderId().toString(),
                        "Order payment reward, orderId=" + event.getOrderId());
            }
            log.info("Awarded {} points for orderId={}", points, event.getOrderId());
        } catch (Exception e) {
            // Failure only logged, never persisted for retry
            log.error("Failed to award points for orderId={}: {}", event.getOrderId(), e.getMessage(), e);
        }
    }
}
