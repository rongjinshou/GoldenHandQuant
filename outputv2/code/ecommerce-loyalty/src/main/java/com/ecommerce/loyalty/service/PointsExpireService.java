package com.ecommerce.loyalty.service;

import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.PointsTransaction;
import com.ecommerce.loyalty.entity.PointsTransactionType;
import com.ecommerce.loyalty.repository.LoyaltyAccountRepository;
import com.ecommerce.loyalty.repository.PointsTransactionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Handles the periodic expiration of loyalty points.
 *
 * <p>design-docs/12-积分与会员服务设计.md §4: points are valid for 12 calendar
 * months; on the 1st of every month, a batch scan finds expired points,
 * deducts them, and records the deduction. Previously {@link #expire()} was
 * a complete no-op with no scheduling (design spec §6.9 item 4).
 *
 * <p>Each EARN {@link PointsTransaction} carries its own {@code expiresAt}
 * (set 12 months out when awarded — see {@link LoyaltyPointService#earnPoints}).
 * This scan finds EARN transactions whose {@code expiresAt} has passed and
 * that have not yet been processed, and deducts the corresponding amount
 * from each affected user's available balance — capped at their current
 * balance, since some of those earned points may already have been spent
 * via redemption (design-docs/12 §4: "积分抵扣时不得使用已过期积分" — expired
 * points must never be usable, so once spent they cannot expire again).
 */
@Service
public class PointsExpireService {

    private static final Logger log = LoggerFactory.getLogger(PointsExpireService.class);

    private final LoyaltyAccountRepository accountRepository;
    private final PointsTransactionRepository transactionRepository;

    public PointsExpireService(LoyaltyAccountRepository accountRepository,
                                PointsTransactionRepository transactionRepository) {
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
    }

    /**
     * Runs the points expiration task: scans for EARN transactions past
     * their expiry date, deducts the expired amount from each affected
     * user's balance, and records an EXPIRE transaction per user.
     *
     * <p>Scheduled for 00:00 on the 1st of every month (design-docs/12 §4);
     * also invocable on demand via
     * {@code POST /api/v1/admin/loyalty/points/expire}.
     */
    @Scheduled(cron = "0 0 0 1 * *")
    @Transactional
    public void expire() {
        LocalDateTime cutoff = SystemClockService.now();
        List<PointsTransaction> expirable = transactionRepository
                .findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(PointsTransactionType.EARN, cutoff);

        if (expirable.isEmpty()) {
            log.info("PointsExpireService.expire(): no expirable points found as of {}", cutoff);
            return;
        }

        Map<Long, List<PointsTransaction>> byUser = expirable.stream()
                .collect(Collectors.groupingBy(PointsTransaction::getUserId));

        byUser.forEach(this::expireForUser);

        log.info("PointsExpireService.expire(): processed {} user(s), {} transaction(s)",
                byUser.size(), expirable.size());
    }

    private void expireForUser(Long userId, List<PointsTransaction> earnTransactions) {
        LoyaltyAccount account = accountRepository.findByUserId(userId).orElse(null);
        if (account == null) {
            log.warn("PointsExpireService: no loyalty account for userId={}, marking {} transaction(s) processed",
                    userId, earnTransactions.size());
            earnTransactions.forEach(tx -> tx.setExpired(true));
            transactionRepository.saveAll(earnTransactions);
            return;
        }

        int totalEligible = earnTransactions.stream().mapToInt(PointsTransaction::getAmount).sum();
        // Cap at the currently-available balance: some of the earned points
        // may already have been redeemed since they were earned.
        int toExpire = Math.min(totalEligible, account.getAvailablePoints());

        earnTransactions.forEach(tx -> tx.setExpired(true));
        transactionRepository.saveAll(earnTransactions);

        if (toExpire <= 0) {
            log.info("PointsExpireService: userId={} eligible points already spent, nothing to deduct", userId);
            return;
        }

        account.setAvailablePoints(account.getAvailablePoints() - toExpire);
        account.setTotalPoints(account.getTotalPoints() - toExpire);
        account.setExpiredPoints(account.getExpiredPoints() + toExpire);
        accountRepository.save(account);

        PointsTransaction expireTx = new PointsTransaction();
        expireTx.setUserId(userId);
        expireTx.setType(PointsTransactionType.EXPIRE);
        expireTx.setAmount(-toExpire);
        expireTx.setBalance(account.getAvailablePoints());
        expireTx.setBizType("POINTS_EXPIRE");
        expireTx.setDescription("Points expired: " + toExpire + " points past the validity window");
        expireTx.setExpired(true);
        transactionRepository.save(expireTx);

        log.info("PointsExpireService: expired {} points for userId={}, new balance={}",
                toExpire, userId, account.getAvailablePoints());
    }
}
