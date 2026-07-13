package com.ecommerce.loyalty.service;

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

import java.lang.annotation.Annotation;
import java.lang.reflect.Method;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link PointsExpireService}.
 *
 * <p>design spec §6.9 item 4: {@code expire()} was previously a complete
 * no-op with no scheduling. It must now actually scan for expired EARN
 * transactions, deduct the corresponding amount from each user's balance
 * (capped at their available balance), record an EXPIRE transaction, and
 * run on a monthly schedule (design-docs/12 §4).
 */
@ExtendWith(MockitoExtension.class)
class PointsExpireServiceTest {

    @Mock
    private LoyaltyAccountRepository accountRepository;

    @Mock
    private PointsTransactionRepository transactionRepository;

    private PointsExpireService pointsExpireService;

    @BeforeEach
    void setUp() {
        pointsExpireService = new PointsExpireService(accountRepository, transactionRepository);
    }

    @AfterEach
    void tearDown() {
        SystemClockService.reset();
    }

    @Test
    void testExpire_noEligibleTransactions_isNoOp() {
        when(transactionRepository.findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
                eq(PointsTransactionType.EARN), any())).thenReturn(List.of());

        pointsExpireService.expire();

        verify(accountRepository, never()).save(any());
        verify(transactionRepository, never()).save(any());
    }

    @Test
    void testExpire_deductsEligiblePoints_andRecordsExpireTransaction() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 7, 1, 0, 0));
        Long userId = 42L;
        LoyaltyAccount account = account(userId, 5000, 5000);
        PointsTransaction earn = earnTx(userId, 1200, LocalDateTime.of(2026, 6, 30, 0, 0));

        when(transactionRepository.findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
                eq(PointsTransactionType.EARN), any())).thenReturn(List.of(earn));
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));

        pointsExpireService.expire();

        assertTrue(earn.isExpired(), "The processed EARN transaction must be marked expired");
        verify(transactionRepository).saveAll(anyList());

        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        LoyaltyAccount saved = accountCaptor.getValue();
        assertEquals(3800, saved.getAvailablePoints(), "5000 - 1200 expired = 3800");
        assertEquals(3800, saved.getTotalPoints());
        assertEquals(1200, saved.getExpiredPoints());

        ArgumentCaptor<PointsTransaction> txCaptor = ArgumentCaptor.forClass(PointsTransaction.class);
        verify(transactionRepository).save(txCaptor.capture());
        PointsTransaction expireTx = txCaptor.getValue();
        assertEquals(PointsTransactionType.EXPIRE, expireTx.getType());
        assertEquals(-1200, expireTx.getAmount());
        assertEquals(3800, expireTx.getBalance());
        assertEquals(userId, expireTx.getUserId());
    }

    /**
     * design-docs/12 §4: expired points must never be usable. If the earned
     * points were already redeemed before their expiry date, the deduction
     * must be capped at the current available balance (never driving it
     * negative).
     */
    @Test
    void testExpire_capsDeductionAtAvailableBalance() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 7, 1, 0, 0));
        Long userId = 7L;
        // Account only has 300 available (the rest of the 1000 earned was
        // already redeemed before expiring).
        LoyaltyAccount account = account(userId, 300, 300);
        PointsTransaction earn = earnTx(userId, 1000, LocalDateTime.of(2026, 6, 1, 0, 0));

        when(transactionRepository.findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
                eq(PointsTransactionType.EARN), any())).thenReturn(List.of(earn));
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));

        pointsExpireService.expire();

        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        assertEquals(0, accountCaptor.getValue().getAvailablePoints(),
                "Deduction must be capped at the available balance, never negative");
        assertEquals(300, accountCaptor.getValue().getExpiredPoints());
    }

    @Test
    void testExpire_multipleEarnBatchesForSameUser_sumBeforeCapping() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 7, 1, 0, 0));
        Long userId = 9L;
        LoyaltyAccount account = account(userId, 10000, 10000);
        PointsTransaction earn1 = earnTx(userId, 400, LocalDateTime.of(2026, 5, 1, 0, 0));
        PointsTransaction earn2 = earnTx(userId, 600, LocalDateTime.of(2026, 6, 1, 0, 0));

        when(transactionRepository.findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
                eq(PointsTransactionType.EARN), any())).thenReturn(List.of(earn1, earn2));
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));

        pointsExpireService.expire();

        assertTrue(earn1.isExpired());
        assertTrue(earn2.isExpired());

        ArgumentCaptor<LoyaltyAccount> accountCaptor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(accountCaptor.capture());
        assertEquals(9000, accountCaptor.getValue().getAvailablePoints(), "10000 - (400+600) = 9000");
    }

    /**
     * design-docs/12 §4: the scan must run automatically on the 1st of
     * every month at midnight.
     */
    @Test
    void testExpire_isScheduledMonthlyAtMidnight() throws NoSuchMethodException {
        Method expireMethod = PointsExpireService.class.getMethod("expire");
        org.springframework.scheduling.annotation.Scheduled scheduled =
                findScheduledAnnotation(expireMethod);

        assertNotNull(scheduled, "expire() must be annotated with @Scheduled");
        assertEquals("0 0 0 1 * *", scheduled.cron(),
                "expire() must run at 00:00 on the 1st of every month");
    }

    private org.springframework.scheduling.annotation.Scheduled findScheduledAnnotation(Method method) {
        for (Annotation annotation : method.getAnnotations()) {
            if (annotation instanceof org.springframework.scheduling.annotation.Scheduled) {
                return (org.springframework.scheduling.annotation.Scheduled) annotation;
            }
        }
        return null;
    }

    private LoyaltyAccount account(Long userId, int totalPoints, int availablePoints) {
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        account.setMemberLevel(MemberLevel.NORMAL);
        account.setTotalPoints(totalPoints);
        account.setAvailablePoints(availablePoints);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        account.setAnnualConsumption(BigDecimal.ZERO);
        return account;
    }

    private PointsTransaction earnTx(Long userId, int amount, LocalDateTime expiresAt) {
        PointsTransaction tx = new PointsTransaction();
        tx.setUserId(userId);
        tx.setType(PointsTransactionType.EARN);
        tx.setAmount(amount);
        tx.setBalance(amount);
        tx.setBizType("ORDER");
        tx.setExpiresAt(expiresAt);
        tx.setExpired(false);
        return tx;
    }
}
