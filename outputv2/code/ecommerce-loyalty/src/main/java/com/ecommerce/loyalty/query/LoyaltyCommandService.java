package com.ecommerce.loyalty.query;

import java.math.BigDecimal;

/**
 * Write-side interface for loyalty commands.
 * Implemented by {@link com.ecommerce.loyalty.service.LoyaltyPointService}
 * and {@link com.ecommerce.loyalty.service.PointsExpireService}.
 */
public interface LoyaltyCommandService {

    /**
     * Award points on order payment success.
     *
     * <p>Calculation: orderAmount * levelMultiplier * activityMultiplier.
     *
     * @param userId             the user ID
     * @param orderAmount        the order's payable amount
     * @param activityMultiplier promotional activity multiplier (default 1.0)
     * @return the number of points earned
     */
    int earnPaymentPoints(Long userId, BigDecimal orderAmount, double activityMultiplier);

    /**
     * Redeem points toward an order payment.
     *
     * <p>Applies the 10,000-point cap and 50%-of-order-amount cap.
     *
     * @param userId      the user ID
     * @param points      the number of points the user wishes to redeem
     * @param orderAmount the order's payable amount
     * @param orderId     the order consuming the points; recorded on the
     *                    REDEEM transaction so the deduction can be given
     *                    back if that order is later cancelled
     * @return the number of points actually redeemed
     */
    int redeemPoints(Long userId, int points, BigDecimal orderAmount, Long orderId);

    /**
     * Give back the points a cancelled order had redeemed at creation time.
     *
     * <p>Looks up the REDEEM transaction(s) recorded against {@code orderId}
     * and reverses them: the available/total balances are restored and a
     * REFUND transaction is written. Idempotent — an order whose deduction
     * was already given back, or that never redeemed any points, is a no-op
     * returning 0. Never throws in normal operation: the order module calls
     * this best-effort on its cancellation paths and a refund failure must
     * not block the cancellation itself.
     *
     * @param orderId the cancelled order's id
     * @return the number of points given back (0 if nothing to refund)
     */
    int refundPointsForOrder(Long orderId);

    /**
     * Process expired points. Points older than the configured expire-months
     * should be moved from available to expired balance.
     */
    void expirePoints();
}
