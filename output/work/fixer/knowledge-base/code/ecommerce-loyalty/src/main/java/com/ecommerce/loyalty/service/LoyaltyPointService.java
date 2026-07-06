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
     * Fallback used for both the earn-side rate and the redeem-side
     * exchange rate (100 points = 1 yuan) when
     * {@code loyalty.redeem-rate} has no runtime override
     * (design-docs/附录B §1: default 100). Overridable via
     * {@link #pointsPerYuan()} — design spec §6.9 item 9.
     */
    private static final int DEFAULT_POINTS_PER_YUAN = 100;

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
    public int redeemPoints(Long userId, int points, BigDecimal orderAmount) {
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
        tx.setDescription("Points redeem, deducted " + actual + " points");
        tx.setExpiresAt(null);
        transactionRepository.save(tx);

        log.info("Redeemed {} points for userId={}, balance={}", actual, userId, account.getAvailablePoints());
        return actual;
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
        BigDecimal points = amount.multiply(BigDecimal.valueOf(pointsPerYuan()))
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

    // ======================== Runtime-configurable constants ========================
    //
    // design spec §6.9 item 9: these four values were previously hardcoded
    // constants with no way to override them at runtime; design-docs/附录B
    // §1 lists them as configurable (loyalty.redeem-rate,
    // loyalty.max-redeem-points-per-order, loyalty.max-redeem-ratio,
    // loyalty.expire-months). The current default VALUES were judged
    // correct as-is (§6.9 #9) — only the "hardcoded, no override" defect is
    // fixed here; the fallback below is unchanged from the prior constant.
    //
    // NOTE: 附录B also separately lists `loyalty.points-per-yuan` (default 1)
    // as distinct from `loyalty.redeem-rate` (default 100). The
    // implementation has only ever had a single constant (100) shared by
    // both the earn formula and the redeem-ratio-cap formula; §6.9 #9
    // explicitly adjudicates the current default as correct, so this fix
    // preserves that single shared constant (bound to `loyalty.redeem-rate`,
    // matching its value) rather than introducing a separate
    // `loyalty.points-per-yuan`-driven divisor for earning, which would be
    // a much larger, unreviewed behavioral change outside this item's scope.

    private int pointsPerYuan() {
        return RuntimeConfigRegistry.getInt("loyalty.redeem-rate", DEFAULT_POINTS_PER_YUAN);
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
