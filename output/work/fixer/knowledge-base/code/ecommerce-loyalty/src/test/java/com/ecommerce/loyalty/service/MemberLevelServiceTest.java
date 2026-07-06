package com.ecommerce.loyalty.service;

import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
import com.ecommerce.loyalty.repository.LoyaltyAccountRepository;
import com.ecommerce.loyalty.repository.OrderDataFetcher;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link MemberLevelService}.
 *
 * <p>The service depends on {@link OrderDataFetcher} for the user's tracked
 * annual consumption; see {@code com.ecommerce.loyalty.repository.OrderDataFetcherTest}
 * for how that class itself computes the figure without querying another
 * module's table.
 */
@ExtendWith(MockitoExtension.class)
class MemberLevelServiceTest {

    @Mock
    private LoyaltyAccountRepository accountRepository;

    @Mock
    private OrderDataFetcher orderDataFetcher;

    private MemberLevelService service;

    @BeforeEach
    void setUp() {
        service = new MemberLevelService(accountRepository, orderDataFetcher);
    }

    @Test
    void testEvaluateAndUpgrade_platinumThreshold() {
        Long userId = 1L;
        LoyaltyAccount account = createAccount(userId, MemberLevel.SILVER);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("25000"));

        MemberLevel result = service.evaluateAndUpgrade(userId);

        assertEquals(MemberLevel.PLATINUM, result,
                "Annual consumption 25000 >= 20000 threshold should result in PLATINUM");

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(MemberLevel.PLATINUM, captor.getValue().getMemberLevel(),
                "Account member level should be upgraded to PLATINUM");
    }

    @Test
    void testEvaluateAndUpgrade_goldThreshold() {
        Long userId = 2L;
        LoyaltyAccount account = createAccount(userId, MemberLevel.SILVER);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("6000"));

        MemberLevel result = service.evaluateAndUpgrade(userId);

        assertEquals(MemberLevel.GOLD, result,
                "Annual consumption 6000 >= 5000 threshold should result in GOLD");

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(MemberLevel.GOLD, captor.getValue().getMemberLevel(),
                "Account member level should be upgraded to GOLD");
    }

    @Test
    void testEvaluateAndUpgrade_silverThreshold() {
        Long userId = 3L;
        LoyaltyAccount account = createAccount(userId, MemberLevel.NORMAL);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("1500"));

        MemberLevel result = service.evaluateAndUpgrade(userId);

        assertEquals(MemberLevel.SILVER, result,
                "Annual consumption 1500 >= 1000 threshold should result in SILVER");

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(MemberLevel.SILVER, captor.getValue().getMemberLevel(),
                "Account member level should be upgraded to SILVER");
    }

    @Test
    void testEvaluateAndUpgrade_defaultNormal() {
        Long userId = 4L;
        LoyaltyAccount account = createAccount(userId, MemberLevel.NORMAL);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("500"));

        MemberLevel result = service.evaluateAndUpgrade(userId);

        assertEquals(MemberLevel.NORMAL, result,
                "Annual consumption 500 < 1000 threshold should remain NORMAL");

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(MemberLevel.NORMAL, captor.getValue().getMemberLevel(),
                "Account member level should stay NORMAL");
    }

    /**
     * Verifies that MemberLevelService delegates to OrderDataFetcher (its
     * in-module-only data source, per design spec §6.9 item 5) to obtain
     * the user's tracked annual consumption before computing the level.
     */
    @Test
    void testLevelCalculation_usesLocalDataFetcher() {
        Long userId = 5L;
        LoyaltyAccount account = createAccount(userId, MemberLevel.SILVER);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("8000"));

        MemberLevel result = service.evaluateAndUpgrade(userId);

        verify(orderDataFetcher).getAnnualConsumption(eq(userId));
        assertEquals(MemberLevel.GOLD, result);
    }

    /**
     * design spec §6.9 item 11: recordPaymentAndEvaluate must record the
     * payment against the tracked annual consumption BEFORE evaluating the
     * member level, so a tier crossed by this very payment already applies.
     */
    @Test
    void testRecordPaymentAndEvaluate_recordsThenEvaluates() {
        Long userId = 6L;
        BigDecimal paidAmount = new BigDecimal("6000");
        LoyaltyAccount account = createAccount(userId, MemberLevel.NORMAL);
        when(accountRepository.findByUserId(userId)).thenReturn(Optional.of(account));
        when(orderDataFetcher.getAnnualConsumption(userId)).thenReturn(new BigDecimal("6000"));

        MemberLevel result = service.recordPaymentAndEvaluate(userId, paidAmount);

        InOrder inOrder = org.mockito.Mockito.inOrder(orderDataFetcher);
        inOrder.verify(orderDataFetcher).recordPayment(userId, paidAmount);
        inOrder.verify(orderDataFetcher).getAnnualConsumption(userId);

        assertEquals(MemberLevel.GOLD, result,
                "Recording a 6000 payment should evaluate to GOLD (>= 5000 threshold)");
    }

    private LoyaltyAccount createAccount(Long userId, MemberLevel level) {
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        account.setMemberLevel(level);
        account.setTotalPoints(0);
        account.setAvailablePoints(0);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        account.setAnnualConsumption(BigDecimal.ZERO);
        return account;
    }
}
