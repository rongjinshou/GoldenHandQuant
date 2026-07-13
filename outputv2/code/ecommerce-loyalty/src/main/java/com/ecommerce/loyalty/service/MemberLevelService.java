package com.ecommerce.loyalty.service;

import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
import com.ecommerce.loyalty.repository.LoyaltyAccountRepository;
import com.ecommerce.loyalty.repository.OrderDataFetcher;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Optional;

/**
 * Evaluates and upgrades a user's membership level based on annual consumption.
 */
@Service
public class MemberLevelService {

    private static final Logger log = LoggerFactory.getLogger(MemberLevelService.class);

    private static final BigDecimal PLATINUM_THRESHOLD = new BigDecimal("20000");
    private static final BigDecimal GOLD_THRESHOLD = new BigDecimal("5000");
    private static final BigDecimal SILVER_THRESHOLD = new BigDecimal("1000");

    private final LoyaltyAccountRepository accountRepository;

    private final OrderDataFetcher orderDataFetcher;

    public MemberLevelService(LoyaltyAccountRepository accountRepository,
                              OrderDataFetcher orderDataFetcher) {
        this.accountRepository = accountRepository;
        this.orderDataFetcher = orderDataFetcher;
    }

    /**
     * Records a newly paid order against the user's running annual
     * consumption (via {@link OrderDataFetcher#recordPayment}) and then
     * immediately re-evaluates their member level.
     *
     * <p>Callers that award points for this same payment (e.g.
     * {@link com.ecommerce.loyalty.event.OrderPaidEventListener}) MUST call
     * this before scoring, so a tier crossed by this very payment already
     * applies to it (design spec §6.9 item 11: member level was previously
     * only refreshed when {@code GET /member-level} was queried, never at
     * payment time).
     *
     * @param userId     the user ID
     * @param paidAmount the order's paid amount
     * @return the new (or unchanged) membership level
     */
    @Transactional
    public MemberLevel recordPaymentAndEvaluate(Long userId, BigDecimal paidAmount) {
        orderDataFetcher.recordPayment(userId, paidAmount);
        return evaluateAndUpgrade(userId);
    }

    /**
     * Evaluate the user's annual consumption and upgrade their membership
     * level if thresholds are met.
     *
     * <p>Thresholds:
     * <ul>
     *   <li>PLATINUM: annual consumption >= 20,000</li>
     *   <li>GOLD:    annual consumption >= 5,000</li>
     *   <li>SILVER:  annual consumption >= 1,000</li>
     *   <li>NORMAL:  otherwise</li>
     * </ul>
     *
     * @param userId the user ID
     * @return the new (or unchanged) membership level
     */
    @Transactional
    public MemberLevel evaluateAndUpgrade(Long userId) {
        BigDecimal annual = orderDataFetcher.getAnnualConsumption(userId);

        MemberLevel newLevel;
        if (annual.compareTo(PLATINUM_THRESHOLD) >= 0) {
            newLevel = MemberLevel.PLATINUM;
        } else if (annual.compareTo(GOLD_THRESHOLD) >= 0) {
            newLevel = MemberLevel.GOLD;
        } else if (annual.compareTo(SILVER_THRESHOLD) >= 0) {
            newLevel = MemberLevel.SILVER;
        } else {
            newLevel = MemberLevel.NORMAL;
        }

        LoyaltyAccount account = getOrCreateAccount(userId);
        MemberLevel oldLevel = account.getMemberLevel();
        account.setAnnualConsumption(annual);
        account.setMemberLevel(newLevel);
        accountRepository.save(account);

        if (oldLevel != newLevel) {
            log.info("User {} membership upgraded: {} -> {}", userId, oldLevel, newLevel);
        }

        return newLevel;
    }

    /**
     * How many more points the account needs to reach the next membership
     * tier.
     *
     * <p>design-docs/12 §5 defines the tiers by annual consumption
     * (SILVER 1,000 / GOLD 5,000 / PLATINUM 20,000 yuan) and §2 defines the
     * earn rate as 1 point per yuan of paid amount, so the remaining
     * consumption gap and the remaining points gap are the same number:
     * {@code nextTierThreshold - annualConsumption}, rounded up to a whole
     * point and floored at 0. PLATINUM is the highest tier, so its gap is 0.
     *
     * @param level             the account's current member level
     * @param annualConsumption the account's running annual consumption
     *                          ({@code null} is treated as 0)
     * @return the points still needed for the next tier (0 at the top tier)
     */
    public int pointsToNextLevel(MemberLevel level, BigDecimal annualConsumption) {
        BigDecimal nextThreshold;
        switch (level) {
            case NORMAL:
                nextThreshold = SILVER_THRESHOLD;
                break;
            case SILVER:
                nextThreshold = GOLD_THRESHOLD;
                break;
            case GOLD:
                nextThreshold = PLATINUM_THRESHOLD;
                break;
            default:
                // PLATINUM — already at the highest tier.
                return 0;
        }
        BigDecimal consumed = annualConsumption != null ? annualConsumption : BigDecimal.ZERO;
        BigDecimal gap = nextThreshold.subtract(consumed);
        if (gap.compareTo(BigDecimal.ZERO) <= 0) {
            return 0;
        }
        return gap.setScale(0, RoundingMode.CEILING).intValue();
    }

    private LoyaltyAccount getOrCreateAccount(Long userId) {
        Optional<LoyaltyAccount> existing = accountRepository.findByUserId(userId);
        if (existing.isPresent()) {
            return existing.get();
        }
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        account.setTotalPoints(0);
        account.setAvailablePoints(0);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        account.setMemberLevel(MemberLevel.NORMAL);
        account.setAnnualConsumption(BigDecimal.ZERO);
        return accountRepository.save(account);
    }
}
