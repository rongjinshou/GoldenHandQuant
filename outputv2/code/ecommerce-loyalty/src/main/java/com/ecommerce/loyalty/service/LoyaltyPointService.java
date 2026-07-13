package com.ecommerce.loyalty.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
import com.ecommerce.loyalty.entity.PointsTransaction;
import com.ecommerce.loyalty.entity.PointsTransactionType;
import com.ecommerce.loyalty.query.LoyaltyCommandService;
import com.ecommerce.loyalty.query.LoyaltyQueryService;
import com.ecommerce.loyalty.repository.LoyaltyAccountRepository;
import com.ecommerce.loyalty.repository.PointsTransactionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * Core service for points operations: query, earn, redeem, and estimate.
 *
 * <p>Implements both {@link LoyaltyQueryService} (reads) and
 * {@link LoyaltyCommandService} (writes).
 */
@Service
public class LoyaltyPointService implements LoyaltyQueryService, LoyaltyCommandService {

    private static final Logger log = LoggerFactory.getLogger(LoyaltyPointService.class);

    /**
     * Fallback for the REDEEM-side exchange rate (100 points = 1 yuan) when
     * {@code loyalty.redeem-rate} has no runtime override
     * (design-docs/附录B §1: default 100). Used only by {@link #pointsPerYuan()}
     * for the redeem-ratio cap (12§3) and points→amount conversion.
     */
    private static final int DEFAULT_POINTS_PER_YUAN = 100;

    /**
     * Fallback for the EARN-side rate ({@code loyalty.points-per-yuan},
     * design-docs/附录B §1: default 1). Per design-docs/12 §2 the earn formula
     * is "实付金额 × 会员等级倍率 × 活动系数" (i.e. 1 point per yuan) — a
     * DIFFERENT rate from the redeem exchange rate above; the two must not be
     * conflated. Used by {@link #earnRatePerYuan()}.
     */
    private static final int DEFAULT_EARN_RATE_PER_YUAN = 1;

    /** Fallback for the maximum redeemable points per order (design-docs/附录B §1: default 10,000). */
    private static final int DEFAULT_MAX_REDEEM_POINTS = 10_000;

    /** Fallback for the maximum redeem ratio (design-docs/附录B §1: default 0.5, i.e. 50% of order amount). */
    private static final BigDecimal DEFAULT_MAX_REDEEM_RATIO = new BigDecimal("0.5");

    /** Fallback for the points validity window in months (design-docs/附录B §1: default 12). */
    private static final int DEFAULT_EXPIRE_MONTHS = 12;

    private final LoyaltyAccountRepository accountRepository;
    private final PointsTransactionRepository transactionRepository;

    public LoyaltyPointService(LoyaltyAccountRepository accountRepository,
                               PointsTransactionRepository transactionRepository) {
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
    }

    // ======================== LoyaltyQueryService ========================

    @Override
    public int getAvailablePoints(Long userId) {
        LoyaltyAccount account = getAccount(userId);
        return account.getAvailablePoints();
    }

    @Override
    public int estimateRedeemPoints(BigDecimal orderAmount, Long userId) {
        LoyaltyAccount account = getAccount(userId);
        int available = account.getAvailablePoints();

        // 50% of order amount in points: orderAmount * 100 * 0.5
        int ratioCapped = orderAmount.multiply(BigDecimal.valueOf(pointsPerYuan()))
                .multiply(maxRedeemRatio())
                .setScale(0, RoundingMode.DOWN)
                .intValue();

        // min(available, maxRedeemPoints, ratioCapped)
        return Math.min(Math.min(available, maxRedeemPoints()), ratioCapped);
    }

    @Override
    public MemberLevel getMemberLevel(Long userId) {
        LoyaltyAccount account = getAccount(userId);
        return account.getMemberLevel();
    }

    @Override
    public double getMemberMultiplier(Long userId) {
        LoyaltyAccount account = getAccount(userId);
        return account.getMemberLevel().getMultiplier();
    }

    // ======================== LoyaltyCommandService ========================

    @Override
    @Transactional
    public int earnPaymentPoints(Long userId, BigDecimal orderAmount, double activityMultiplier) {
        int points = calcOrderPoints(orderAmount, userId, activityMultiplier);
        if (points <= 0) {
            return 0;
        }
        earnPoints(userId, points, "ORDER_PAYMENT", null, "Order payment reward");
        return points;
    }

    @Override
    @Transactional
    public int redeemPoints(Long userId, int points, BigDecimal orderAmount, Long orderId) {
        LoyaltyAccount account = getAccount(userId);

        // Apply 10,000 cap and 50% cap
        int maxRedeemable = estimateRedeemPoints(orderAmount, userId);
        int actual = Math.min(points, maxRedeemable);

        if (actual <= 0) {
            return 0;
        }

        account.setAvailablePoints(account.getAvailablePoints() - actual);
        account.setRedeemedPoints(account.getRedeemedPoints() + actual);
        account.setTotalPoints(account.getTotalPoints() - actual);
        accountRepository.save(account);

        PointsTransaction tx = new PointsTransaction();
        tx.setUserId(userId);
        tx.setType(PointsTransactionType.REDEEM);
        tx.setAmount(-actual);
        tx.setBalance(account.getAvailablePoints());
        tx.setBizType("ORDER_REDEEM");
        // Record which order consumed the points, so refundPointsForOrder can
        // reverse exactly this deduction if that order is cancelled.
        tx.setBizId(orderId != null ? String.valueOf(orderId) : null);
        tx.setDescription("Points redeem, deducted " + actual + " points");
        tx.setExpiresAt(null);
        transactionRepository.save(tx);

        log.info("Redeemed {} points for userId={} on order {}, balance={}",
                actual, userId, orderId, account.getAvailablePoints());
        return actual;
    }

    /**
     * {@inheritDoc}
     *
     * <p>The refund is derived from the loyalty ledger itself — the REDEEM
     * rows {@link #redeemPoints} recorded with the order's id as
     * {@code bizId} — never from a caller-supplied amount, so it always gives
     * back exactly what was actually deducted. Like the promotion-side
     * {@code releaseForOrder} methods, the body deliberately never throws in
     * normal operation ("no deduction for this order" is a legal empty
     * result): the order module invokes it inside its cancellation
     * transaction, and a refund failure must never block the cancellation.
     */
    @Override
    @Transactional
    public int refundPointsForOrder(Long orderId) {
        if (orderId == null) {
            return 0;
        }
        String bizId = String.valueOf(orderId);

        // Idempotency guard: this order's deduction was already given back.
        if (transactionRepository.existsByTypeAndBizId(PointsTransactionType.REFUND, bizId)) {
            return 0;
        }

        List<PointsTransaction> redeems =
                transactionRepository.findByTypeAndBizId(PointsTransactionType.REDEEM, bizId);
        int points = redeems.stream().mapToInt(tx -> -tx.getAmount()).sum();
        if (points <= 0) {
            // The order never redeemed any points — a perfectly normal no-op.
            return 0;
        }

        Long userId = redeems.get(0).getUserId();
        LoyaltyAccount account = getAccount(userId);
        account.setAvailablePoints(account.getAvailablePoints() + points);
        account.setRedeemedPoints(Math.max(0, account.getRedeemedPoints() - points));
        account.setTotalPoints(account.getTotalPoints() + points);
        accountRepository.save(account);

        PointsTransaction tx = new PointsTransaction();
        tx.setUserId(userId);
        tx.setType(PointsTransactionType.REFUND);
        tx.setAmount(points);
        tx.setBalance(account.getAvailablePoints());
        tx.setBizType("ORDER_CANCEL_REFUND");
        tx.setBizId(bizId);
        tx.setDescription("Points refunded for cancelled order " + orderId);
        tx.setExpiresAt(null);
        transactionRepository.save(tx);

        log.info("Refunded {} redeemed points to userId={} for cancelled order {}, balance={}",
                points, userId, orderId, account.getAvailablePoints());
        return points;
    }

    @Override
    public void expirePoints() {
        // Delegated to PointsExpireService
    }

    // ======================== Domain methods ========================

    /**
     * Calculate order points.
     *
     * <p>The calculation multiplies the paid amount by the points-per-yuan
     * rate, member-level multiplier, request activity multiplier, and runtime
     * configured activity multiplier.
     *
     * @param amount             the order payable amount
     * @param userId             the user ID
     * @param activityMultiplier promotional activity coefficient (default 1.0)
     * @return calculated points
     */
    public int calcOrderPoints(BigDecimal amount, Long userId, double activityMultiplier) {
        LoyaltyAccount account = getAccount(userId);
        BigDecimal levelMultiplier = BigDecimal.valueOf(account.getMemberLevel().getMultiplier());
        double configuredActivityMultiplier =
                RuntimeConfigRegistry.getDouble("loyalty.activity-multiplier", 1.0d);
        BigDecimal points = amount.multiply(BigDecimal.valueOf(earnRatePerYuan()))
                .multiply(levelMultiplier)
                .multiply(BigDecimal.valueOf(activityMultiplier))
                .multiply(BigDecimal.valueOf(configuredActivityMultiplier));
        return points.setScale(0, RoundingMode.DOWN).intValue();
    }

    /**
     * Award points to a user and record the transaction.
     *
     * @param userId      the user ID
     * @param points      number of points to add
     * @param bizType     business type (e.g. "ORDER", "REVIEW")
     * @param bizId       business entity ID
     * @param description human-readable description
     */
    @Transactional
    public void earnPoints(Long userId, int points, String bizType, String bizId, String description) {
        // Fault injection check
        if (com.ecommerce.common.test.FaultInjectionRegistry.isActive("loyalty-award-points-failure")) {
            throw new RuntimeException("Fault injected: loyalty-award-points-failure");
        }

        LoyaltyAccount account = getAccount(userId);

        account.setTotalPoints(account.getTotalPoints() + points);
        account.setAvailablePoints(account.getAvailablePoints() + points);
        accountRepository.save(account);

        PointsTransaction tx = new PointsTransaction();
        tx.setUserId(userId);
        tx.setType(PointsTransactionType.EARN);
        tx.setAmount(points);
        tx.setBalance(account.getAvailablePoints());
        tx.setBizType(bizType);
        tx.setBizId(bizId);
        tx.setDescription(description);
        tx.setExpiresAt(SystemClockService.now().plusMonths(expireMonths()));
        transactionRepository.save(tx);

        log.info("Earned {} points for userId={}, balance={}", points, userId, account.getAvailablePoints());
    }

    // ======================== Runtime-configurable rates ========================
    //
    // design-docs/附录B §1 lists TWO distinct loyalty rates that must not be
    // conflated:
    //   • loyalty.points-per-yuan (default 1)  — the EARN rate. 12§2:
    //     订单积分 = 实付金额 × 会员等级倍率 × 活动系数 (i.e. 1 point/yuan).
    //   • loyalty.redeem-rate     (default 100) — the REDEEM exchange rate.
    //     12§3: 100 积分 = 1 元; used for the redeem-ratio cap and for
    //     converting redeemed points back to an amount.
    // (max-redeem-points-per-order / max-redeem-ratio / expire-months are read
    // by their own methods below.)

    /** EARN rate: points awarded per yuan of paid amount (12§2). */
    private int earnRatePerYuan() {
        return RuntimeConfigRegistry.getInt("loyalty.points-per-yuan", DEFAULT_EARN_RATE_PER_YUAN);
    }

    /** REDEEM exchange rate: points that equal one yuan when redeeming (12§3). */
    private int pointsPerYuan() {
        return RuntimeConfigRegistry.getInt("loyalty.redeem-rate", DEFAULT_POINTS_PER_YUAN);
    }

    /**
     * Convert redeemed points to the equivalent deduction amount using the
     * configurable redeem exchange rate (12§3: 抵扣金额 = 实际可用积分 / 兑换比例)
     * and HALF_UP rounding to the cent (03§1). Kept here so the rate stays in
     * one place rather than hardcoded at call sites.
     */
    public BigDecimal pointsToAmount(int points) {
        if (points <= 0) {
            return BigDecimal.ZERO;
        }
        return BigDecimal.valueOf(points)
                .divide(BigDecimal.valueOf(pointsPerYuan()), 2, RoundingMode.HALF_UP);
    }

    private int maxRedeemPoints() {
        return RuntimeConfigRegistry.getInt("loyalty.max-redeem-points-per-order", DEFAULT_MAX_REDEEM_POINTS);
    }

    private BigDecimal maxRedeemRatio() {
        return RuntimeConfigRegistry.getBigDecimal("loyalty.max-redeem-ratio", DEFAULT_MAX_REDEEM_RATIO);
    }

    private int expireMonths() {
        return RuntimeConfigRegistry.getInt("loyalty.expire-months", DEFAULT_EXPIRE_MONTHS);
    }

    // ======================== Helpers ========================

    /**
     * Get the loyalty account for a user, or create one with defaults.
     */
    private LoyaltyAccount getAccount(Long userId) {
        return accountRepository.findByUserId(userId)
                .map(this::applyConfigOverrides)
                .orElseGet(() -> createDefaultAccount(userId));
    }

    private LoyaltyAccount createDefaultAccount(Long userId) {
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        int initialPoints = RuntimeConfigRegistry.getInt("loyalty.points", 0);
        account.setTotalPoints(initialPoints);
        account.setAvailablePoints(initialPoints);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        account.setMemberLevel(resolveConfiguredMemberLevel(MemberLevel.NORMAL));
        account.setAnnualConsumption(BigDecimal.ZERO);
        return accountRepository.save(account);
    }

    private LoyaltyAccount applyConfigOverrides(LoyaltyAccount account) {
        boolean changed = false;
        MemberLevel configuredLevel = resolveConfiguredMemberLevel(account.getMemberLevel());
        if (configuredLevel != account.getMemberLevel()) {
            account.setMemberLevel(configuredLevel);
            changed = true;
        }
        return changed ? accountRepository.save(account) : account;
    }

    private MemberLevel resolveConfiguredMemberLevel(MemberLevel fallback) {
        String configured = RuntimeConfigRegistry.getString("loyalty.member-level", null);
        if (configured == null || configured.isBlank()) {
            return fallback;
        }
        try {
            return MemberLevel.valueOf(configured.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            return fallback;
        }
    }

    /**
     * Exposed so the controller can build a points response.
     */
    public LoyaltyAccount getAccountByUserId(Long userId) {
        return getAccount(userId);
    }
}
