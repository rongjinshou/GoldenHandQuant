package com.ecommerce.loyalty.service;

import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
import com.ecommerce.loyalty.entity.PointsTransaction;
import com.ecommerce.loyalty.entity.PointsTransactionType;
import com.ecommerce.loyalty.repository.LoyaltyAccountRepository;
import com.ecommerce.loyalty.repository.PointsTransactionRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link LoyaltyPointService}.
 */
@ExtendWith(MockitoExtension.class)
class LoyaltyPointServiceTest {

    @Mock
    private LoyaltyAccountRepository accountRepository;

    @Mock
    private PointsTransactionRepository transactionRepository;

    private LoyaltyPointService service;

    @BeforeEach
    void setUp() {
        service = new LoyaltyPointService(accountRepository, transactionRepository);
    }

    @AfterEach
    void tearDown() {
        RuntimeConfigRegistry.clear();
        SystemClockService.reset();
    }

    // ======================== calcOrderPoints ========================

    /**
     * calcOrderPoints applies the activityMultiplier parameter.
     */
    @Test
    void testCalcOrderPoints_withActivityCoefficient() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.SILVER, 0, 0);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        BigDecimal amount = new BigDecimal("100");
        double activityMultiplier = 2.0;

        int result = service.calcOrderPoints(amount, 1L, activityMultiplier);

        // earn uses loyalty.points-per-yuan (12§2, default 1), NOT redeem-rate:
        // 100 yuan * 1 point/yuan * 1.1 (SILVER multiplier) * 2.0 activity multiplier
        int expected = 220;

        assertEquals(expected, result,
                "activityMultiplier=2.0 should double the base order points");
    }

    // ======================== earnPoints ========================

    @Test
    void testEarnPoints_createsTransactionAndUpdatesBalance() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 0, 0);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        service.earnPoints(1L, 500, "TEST_BIZ", "BIZ-001", "Test earn description");

        // Verify account balance was updated
        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        LoyaltyAccount savedAccount = accountCaptor.getValue();
        assertEquals(500, savedAccount.getTotalPoints(), "Total points should increase by 500");
        assertEquals(500, savedAccount.getAvailablePoints(), "Available points should increase by 500");

        // Verify a PointsTransaction record was created
        ArgumentCaptor<PointsTransaction> txCaptor = ArgumentCaptor.forClass(PointsTransaction.class);
        verify(transactionRepository).save(txCaptor.capture());
        PointsTransaction tx = txCaptor.getValue();
        assertEquals(1L, tx.getUserId(), "Transaction userId should match");
        assertEquals(PointsTransactionType.EARN, tx.getType(), "Transaction type should be EARN");
        assertEquals(500, tx.getAmount(), "Transaction amount should be 500");
        assertEquals(500, tx.getBalance(), "Transaction balance should reflect new balance");
        assertEquals("TEST_BIZ", tx.getBizType(), "Transaction bizType should match");
        assertEquals("BIZ-001", tx.getBizId(), "Transaction bizId should match");
        assertEquals("Test earn description", tx.getDescription(), "Transaction description should match");
        assertNotNull(tx.getExpiresAt(), "EARN transaction should have an expiration date");
    }

    // ======================== redeemPoints ========================

    /**
     * Redeem applies both 10,000-point cap and 50%-of-order cap.
     * Within limits, points are deducted correctly.
     */
    @Test
    void testRedeemPoints_withinLimits_deductsPoints() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 5000, 5000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        // orderAmount=100 yuan: 50% cap = 100 * 100 * 0.5 = 5000
        // available=5000, max cap=10000 -> maxRedeemable = min(5000, 10000, 5000) = 5000
        // actual = min(2000, 5000) = 2000
        int redeemed = service.redeemPoints(1L, 2000, BigDecimal.valueOf(100), 900L);

        assertEquals(2000, redeemed, "Should redeem exactly 2000 (within all caps)");

        // Verify account state
        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        LoyaltyAccount saved = accountCaptor.getValue();
        assertEquals(3000, saved.getAvailablePoints(), "Available points should decrease to 3000");
        assertEquals(2000, saved.getRedeemedPoints(), "Redeemed points should increase to 2000");
        assertEquals(3000, saved.getTotalPoints(), "Total points should decrease to 3000");

        // Verify REDEEM transaction was recorded
        ArgumentCaptor<PointsTransaction> txCaptor = ArgumentCaptor.forClass(PointsTransaction.class);
        verify(transactionRepository).save(txCaptor.capture());
        PointsTransaction tx = txCaptor.getValue();
        assertEquals(PointsTransactionType.REDEEM, tx.getType());
        assertEquals(-2000, tx.getAmount());
        assertEquals("ORDER_REDEEM", tx.getBizType());
        assertEquals("900", tx.getBizId(),
                "REDEEM transaction should record the consuming order's id for cancel refunds");
    }

    /**
     * When requested points exceed the calculated maximum
     * (10,000-point cap or 50% cap), the redemption is clamped.
     */
    @Test
    void testRedeemPoints_exceedsCap_clampedToMax() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 50000, 50000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        // orderAmount=100 yuan: 50% cap = 5000
        // available=50000, max=10000 -> maxRedeemable = min(50000, 10000, 5000) = 5000
        // actual = min(50000, 5000) = 5000 (clamped by 50% cap)
        int redeemed = service.redeemPoints(1L, 50000, BigDecimal.valueOf(100), 900L);

        assertEquals(5000, redeemed,
                "Should be clamped to 5000 by 50%-of-order cap (not 50000 as requested)");

        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        LoyaltyAccount saved = accountCaptor.getValue();
        assertEquals(45000, saved.getAvailablePoints(), "Available points should decrease by 5000");
        assertEquals(5000, saved.getRedeemedPoints(), "Redeemed points should be 5000");
    }

    // ======================== refundPointsForOrder ========================

    /**
     * Refunding a cancelled order reverses exactly the ledger's REDEEM rows
     * for that order: balances restored, REFUND transaction written.
     */
    @Test
    void testRefundPointsForOrder_restoresRedeemedPoints() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 3000, 3000);
        account.setRedeemedPoints(2000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        PointsTransaction redeemTx = new PointsTransaction();
        redeemTx.setUserId(1L);
        redeemTx.setType(PointsTransactionType.REDEEM);
        redeemTx.setAmount(-2000);
        redeemTx.setBizType("ORDER_REDEEM");
        redeemTx.setBizId("900");
        when(transactionRepository.existsByTypeAndBizId(PointsTransactionType.REFUND, "900"))
                .thenReturn(false);
        when(transactionRepository.findByTypeAndBizId(PointsTransactionType.REDEEM, "900"))
                .thenReturn(java.util.List.of(redeemTx));

        int refunded = service.refundPointsForOrder(900L);

        assertEquals(2000, refunded, "Should give back exactly the 2000 points the order redeemed");

        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        LoyaltyAccount saved = accountCaptor.getValue();
        assertEquals(5000, saved.getAvailablePoints(), "Available points should be restored to 5000");
        assertEquals(0, saved.getRedeemedPoints(), "Redeemed points should fall back to 0");
        assertEquals(5000, saved.getTotalPoints(), "Total points should be restored to 5000");

        ArgumentCaptor<PointsTransaction> txCaptor = ArgumentCaptor.forClass(PointsTransaction.class);
        verify(transactionRepository).save(txCaptor.capture());
        PointsTransaction tx = txCaptor.getValue();
        assertEquals(PointsTransactionType.REFUND, tx.getType());
        assertEquals(2000, tx.getAmount());
        assertEquals("ORDER_CANCEL_REFUND", tx.getBizType());
        assertEquals("900", tx.getBizId());
    }

    /**
     * Idempotency: once a REFUND row exists for the order, calling again is
     * a pure no-op — no balance change, no second transaction.
     */
    @Test
    void testRefundPointsForOrder_secondCallIsNoop() {
        when(transactionRepository.existsByTypeAndBizId(PointsTransactionType.REFUND, "900"))
                .thenReturn(true);

        int refunded = service.refundPointsForOrder(900L);

        assertEquals(0, refunded, "A second refund for the same order must be a no-op");
        verify(accountRepository, never()).save(any(LoyaltyAccount.class));
        verify(transactionRepository, never()).save(any(PointsTransaction.class));
    }

    /**
     * An order that never redeemed points has no REDEEM rows — refunding it
     * is a legal no-op that must not throw.
     */
    @Test
    void testRefundPointsForOrder_orderWithoutRedeem_isNoop() {
        when(transactionRepository.existsByTypeAndBizId(PointsTransactionType.REFUND, "901"))
                .thenReturn(false);
        when(transactionRepository.findByTypeAndBizId(PointsTransactionType.REDEEM, "901"))
                .thenReturn(java.util.List.of());

        int refunded = service.refundPointsForOrder(901L);

        assertEquals(0, refunded);
        verify(accountRepository, never()).save(any(LoyaltyAccount.class));
        verify(transactionRepository, never()).save(any(PointsTransaction.class));
    }

    // ======================== estimateRedeemPoints ========================

    @Test
    void testEstimateRedeem_returnsCorrectEstimate() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 5000, 5000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        // orderAmount=100 yuan -> 50% cap = 5000; available=5000; max=10000
        // estimate = min(5000, 10000, 5000) = 5000
        int estimate = service.estimateRedeemPoints(BigDecimal.valueOf(100), 1L);
        assertEquals(5000, estimate, "Estimate should be 5000 (limited by 50% cap and available points)");
    }

    // ======================== getAvailablePoints / getAccountByUserId ========================

    @Test
    void testGetPoints_returnsAccountBalance() {
        LoyaltyAccount account = createAccount(2L, MemberLevel.SILVER, 1200, 1200);
        when(accountRepository.findByUserId(2L)).thenReturn(Optional.of(account));

        int points = service.getAvailablePoints(2L);
        assertEquals(1200, points, "Available points should match account balance");

        LoyaltyAccount retrieved = service.getAccountByUserId(2L);
        assertEquals(1200, retrieved.getAvailablePoints(), "Account retrieved should have correct balance");
    }

    // ==================== RuntimeConfigRegistry overrides (§6.9 item 9) ====================
    //
    // design spec §6.9 item 9: the redeem/earn constants (points-per-yuan /
    // redeem-rate, max redeem points, max redeem ratio, expire months) must
    // honor RuntimeConfigRegistry overrides instead of being permanently
    // hardcoded, while defaulting to the same values as before when no
    // override is set (already covered by the tests above).

    @Test
    void testCalcOrderPoints_honorsPointsPerYuanOverride() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 0, 0);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));
        RuntimeConfigRegistry.put("loyalty.points-per-yuan", 10);

        // earn uses loyalty.points-per-yuan (12§2), NOT loyalty.redeem-rate:
        // 100 yuan * 10 points/yuan (overridden) * 1.0 (NORMAL) * 1.0 (activity) = 1000
        int result = service.calcOrderPoints(new BigDecimal("100"), 1L, 1.0);

        assertEquals(1000, result, "calcOrderPoints must honor the loyalty.points-per-yuan override");
    }

    @Test
    void testEstimateRedeem_honorsMaxRedeemPointsOverride() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 50000, 50000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));
        RuntimeConfigRegistry.put("loyalty.max-redeem-points-per-order", 500);

        // ratio cap = 1000*100*0.5 = 50000; available=50000; overridden max=500
        int estimate = service.estimateRedeemPoints(BigDecimal.valueOf(1000), 1L);

        assertEquals(500, estimate, "estimateRedeemPoints must honor the loyalty.max-redeem-points-per-order override");
    }

    @Test
    void testEstimateRedeem_honorsMaxRedeemRatioOverride() {
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 50000, 50000);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));
        RuntimeConfigRegistry.put("loyalty.max-redeem-ratio", "0.1");

        // ratio cap = 100*100*0.1 (overridden) = 1000; available=50000; max=10000
        int estimate = service.estimateRedeemPoints(BigDecimal.valueOf(100), 1L);

        assertEquals(1000, estimate, "estimateRedeemPoints must honor the loyalty.max-redeem-ratio override");
    }

    @Test
    void testEarnPoints_honorsExpireMonthsOverride() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 1, 1, 0, 0));
        LoyaltyAccount account = createAccount(1L, MemberLevel.NORMAL, 0, 0);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));
        RuntimeConfigRegistry.put("loyalty.expire-months", 1);

        service.earnPoints(1L, 100, "TEST", null, "desc");

        ArgumentCaptor<PointsTransaction> txCaptor = ArgumentCaptor.forClass(PointsTransaction.class);
        verify(transactionRepository).save(txCaptor.capture());
        assertEquals(LocalDateTime.of(2026, 2, 1, 0, 0), txCaptor.getValue().getExpiresAt(),
                "expiresAt must reflect the loyalty.expire-months override (1 month), not the default 12");
    }

    // ======================== helpers ========================

    private LoyaltyAccount createAccount(Long userId, MemberLevel level, int totalPoints, int availablePoints) {
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        account.setMemberLevel(level);
        account.setTotalPoints(totalPoints);
        account.setAvailablePoints(availablePoints);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        return account;
    }
}
