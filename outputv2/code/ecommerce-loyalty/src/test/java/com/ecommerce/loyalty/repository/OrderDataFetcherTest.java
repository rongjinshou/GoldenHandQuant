package com.ecommerce.loyalty.repository;

import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.loyalty.entity.LoyaltyAccount;
import com.ecommerce.loyalty.entity.MemberLevel;
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
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link OrderDataFetcher}.
 *
 * <p>design spec §6.9 items 5 and 10: this class must no longer query the
 * {@code orders} table directly (a cross-module boundary violation), and
 * must resolve "now" through {@link SystemClockService} rather than
 * {@code LocalDate.now()} so the black-box test clock override applies.
 */
@ExtendWith(MockitoExtension.class)
class OrderDataFetcherTest {

    @Mock
    private LoyaltyAccountRepository accountRepository;

    private OrderDataFetcher fetcher;

    @BeforeEach
    void setUp() {
        fetcher = new OrderDataFetcher(accountRepository);
    }

    @AfterEach
    void tearDown() {
        SystemClockService.reset();
    }

    @Test
    void testGetAnnualConsumption_noAccount_returnsZero() {
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.empty());

        assertEquals(BigDecimal.ZERO, fetcher.getAnnualConsumption(1L));
    }

    @Test
    void testGetAnnualConsumption_sameYear_returnsTrackedTotal() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 6, 1, 0, 0));
        LoyaltyAccount account = account(1L);
        account.setAnnualConsumption(new BigDecimal("3000"));
        account.setConsumptionYear(2026);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        assertEquals(new BigDecimal("3000"), fetcher.getAnnualConsumption(1L));
    }

    /**
     * A total tracked in a prior year must read as zero (year rollover),
     * rather than incorrectly carrying forward as this year's consumption.
     */
    @Test
    void testGetAnnualConsumption_staleYear_returnsZero() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 1, 15, 0, 0));
        LoyaltyAccount account = account(1L);
        account.setAnnualConsumption(new BigDecimal("25000"));
        account.setConsumptionYear(2025);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        assertEquals(BigDecimal.ZERO, fetcher.getAnnualConsumption(1L),
                "A prior year's tracked total must not carry over into the new year");
    }

    @Test
    void testRecordPayment_accumulatesWithinSameYear() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 3, 1, 0, 0));
        LoyaltyAccount account = account(1L);
        account.setAnnualConsumption(new BigDecimal("1000"));
        account.setConsumptionYear(2026);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        fetcher.recordPayment(1L, new BigDecimal("500"));

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(new BigDecimal("1500"), captor.getValue().getAnnualConsumption());
        assertEquals(2026, captor.getValue().getConsumptionYear());
    }

    /**
     * Recording a payment after a year rollover must reset the running
     * total to just this payment's amount, not add on top of last year's
     * stale figure.
     */
    @Test
    void testRecordPayment_resetsOnYearRollover() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 1, 5, 0, 0));
        LoyaltyAccount account = account(1L);
        account.setAnnualConsumption(new BigDecimal("25000"));
        account.setConsumptionYear(2025);
        when(accountRepository.findByUserId(1L)).thenReturn(Optional.of(account));

        fetcher.recordPayment(1L, new BigDecimal("200"));

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository).save(captor.capture());
        assertEquals(new BigDecimal("200"), captor.getValue().getAnnualConsumption());
        assertEquals(2026, captor.getValue().getConsumptionYear());
    }

    @Test
    void testRecordPayment_createsAccountWhenMissing() {
        SystemClockService.setFixed(LocalDateTime.of(2026, 5, 1, 0, 0));
        when(accountRepository.findByUserId(2L)).thenReturn(Optional.empty());
        when(accountRepository.save(org.mockito.ArgumentMatchers.any(LoyaltyAccount.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        fetcher.recordPayment(2L, new BigDecimal("300"));

        ArgumentCaptor<LoyaltyAccount> captor = ArgumentCaptor.forClass(LoyaltyAccount.class);
        verify(accountRepository, org.mockito.Mockito.times(2)).save(captor.capture());
        LoyaltyAccount saved = captor.getValue();
        assertEquals(new BigDecimal("300"), saved.getAnnualConsumption());
        assertEquals(MemberLevel.NORMAL, saved.getMemberLevel());
    }

    private LoyaltyAccount account(Long userId) {
        LoyaltyAccount account = new LoyaltyAccount();
        account.setUserId(userId);
        account.setMemberLevel(MemberLevel.NORMAL);
        account.setTotalPoints(0);
        account.setAvailablePoints(0);
        account.setFrozenPoints(0);
        account.setRedeemedPoints(0);
        account.setExpiredPoints(0);
        account.setAnnualConsumption(BigDecimal.ZERO);
        return account;
    }
}
