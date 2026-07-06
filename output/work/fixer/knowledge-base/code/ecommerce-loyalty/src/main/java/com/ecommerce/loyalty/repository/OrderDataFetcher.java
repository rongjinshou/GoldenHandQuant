package com.ecommerce.loyalty.repository;

import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;

/**
 * Tracks each user's paid-order consumption for the current calendar year,
 * for use by {@link com.ecommerce.loyalty.service.MemberLevelService}.
 *
 * <p>design-docs/02 §3 and design-docs/12 §5 both forbid the loyalty module
 * from directly accessing the {@code orders} table or the order module's
 * repository; cross-module reads must go through {@code OrderQueryService},
 * an order sales-statistics interface, or "a public local query contract".
 * This class previously violated that rule outright, issuing a raw
 * {@code JdbcTemplate} SQL query against the {@code orders} table.
 *
 * <p><b>Why this isn't a direct {@code OrderQueryService} call:</b> the
 * current {@code OrderQueryService} (ecommerce-order) exposes no per-user
 * annual-consumption/sales-statistics method, and — more fundamentally —
 * {@code ecommerce-order}'s POM already depends on {@code ecommerce-loyalty}
 * (needed for the order/payment side to call {@code LoyaltyCommandService}),
 * so the reverse dependency this module would need to compile against
 * {@code OrderQueryService} directly would form a Maven module cycle. That
 * is a cross-module wiring change outside a loyalty-only change set.
 *
 * <p>Instead, this class implements the "public local query contract"
 * option: loyalty already legitimately receives each {@code OrderPaidEvent}
 * (design-docs/附录D §2), so rather than querying order data at read time,
 * it maintains its own running total — scoped to loyalty's own
 * {@code loyalty_account} row — fed by that event as payments occur
 * (see {@link #recordPayment}). This keeps the computation entirely within
 * loyalty's own bounded context (own table, own column) and needs no
 * cooperation from another module's classpath.
 */
@Component
public class OrderDataFetcher {

    private final LoyaltyAccountRepository accountRepository;

    public OrderDataFetcher(LoyaltyAccountRepository accountRepository) {
        this.accountRepository = accountRepository;
    }

    /**
     * Returns the user's tracked paid-order consumption for the CURRENT
     * calendar year (per {@link SystemClockService}, so the test clock
     * applies — design spec §6.9 item 10). If the account's tracked total
     * belongs to a prior year, it reads as zero (the year has rolled over).
     *
     * @param userId the user ID
     * @return the current calendar year's tracked consumption, or ZERO if
     *         the user has no loyalty account yet
     */
    public BigDecimal getAnnualConsumption(Long userId) {
        return accountRepository.findByUserId(userId)
                .map(this::currentYearConsumption)
                .orElse(BigDecimal.ZERO);
    }

    /**
     * Records a newly paid order's amount against the user's running annual
     * consumption total, resetting it first if the calendar year has rolled
     * over since the last recorded payment.
     *
     * @param userId     the user ID
     * @param paidAmount the order's paid amount (from {@code OrderPaidEvent})
     */
    @Transactional
    public void recordPayment(Long userId, BigDecimal paidAmount) {
        if (userId == null || paidAmount == null) {
            return;
        }
        LoyaltyAccount account = accountRepository.findByUserId(userId)
                .orElseGet(() -> createAccount(userId));

        BigDecimal current = currentYearConsumption(account);
        account.setAnnualConsumption(current.add(paidAmount));
        account.setConsumptionYear(SystemClockService.now().getYear());
        accountRepository.save(account);
    }

    private BigDecimal currentYearConsumption(LoyaltyAccount account) {
        int currentYear = SystemClockService.now().getYear();
        Integer trackedYear = account.getConsumptionYear();
        if (trackedYear == null || trackedYear != currentYear) {
            return BigDecimal.ZERO;
        }
        BigDecimal annual = account.getAnnualConsumption();
        return annual == null ? BigDecimal.ZERO : annual;
    }

    private LoyaltyAccount createAccount(Long userId) {
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
