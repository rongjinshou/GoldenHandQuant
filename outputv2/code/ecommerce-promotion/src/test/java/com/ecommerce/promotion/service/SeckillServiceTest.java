package com.ecommerce.promotion.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.exception.ValidationException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.promotion.dto.SeckillActivityDto;
import com.ecommerce.promotion.entity.SeckillActivity;
import com.ecommerce.promotion.entity.SeckillPurchaseRecord;
import com.ecommerce.promotion.repository.SeckillPurchaseRecordRepository;
import com.ecommerce.promotion.repository.SeckillRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowableOfType;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link SeckillService}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("SeckillService")
class SeckillServiceTest {

    @Mock
    private SeckillRepository seckillRepository;

    @Mock
    private SeckillPurchaseRecordRepository purchaseRecordRepository;

    @InjectMocks
    private SeckillService seckillService;

    @Captor
    private ArgumentCaptor<SeckillActivity> activityCaptor;

    @Captor
    private ArgumentCaptor<SeckillPurchaseRecord> purchaseRecordCaptor;

    // -----------------------------------------------------------------------
    // Shared test data
    // -----------------------------------------------------------------------

    private static final Long USER_ID = 7L;

    private static final Long ORDER_ID = 900L;

    private SeckillActivity activity;

    @BeforeEach
    void setUp() {
        activity = new SeckillActivity();
        activity.setId(1L);
        activity.setName("iPhone Flash Sale");
        activity.setSkuId(100L);
        activity.setSeckillPrice(new BigDecimal("999.00"));
        activity.setStockQuantity(100);
        activity.setSoldQuantity(0);
        activity.setPerUserLimit(1);
        activity.setStartTime(LocalDateTime.now().minusHours(1));
        activity.setEndTime(LocalDateTime.now().plusHours(1));
        activity.setStatus("ACTIVE");
    }

    @AfterEach
    void tearDown() {
        SystemClockService.reset();
    }

    // -----------------------------------------------------------------------
    // Create tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("create")
    class Create {

        @Test
        @DisplayName("create: creates a seckill activity with default values")
        void testCreate_seckillActivity() {
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            SeckillActivityDto result = seckillService.create(activity);

            assertThat(result).isNotNull();
            assertThat(result.getName()).isEqualTo("iPhone Flash Sale");
            assertThat(result.getSeckillPrice()).isEqualByComparingTo(new BigDecimal("999.00"));
            assertThat(result.getStatus()).isEqualTo("ACTIVE");

            verify(seckillRepository).save(activityCaptor.capture());
            SeckillActivity saved = activityCaptor.getValue();
            assertThat(saved.getSoldQuantity()).isEqualTo(0);
            assertThat(saved.getStatus()).isEqualTo("ACTIVE");
        }

        @Test
        @DisplayName("create: sets soldQuantity to 0 and status to ACTIVE")
        void testCreate_setsDefaults() {
            activity.setSoldQuantity(10); // input ignored
            activity.setStatus("INACTIVE"); // input ignored

            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.create(activity);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(0);
            assertThat(activityCaptor.getValue().getStatus()).isEqualTo("ACTIVE");
        }

        @Test
        @DisplayName("create: rejects a second ACTIVE activity for the same SKU with 409 CONFLICT")
        void testCreate_duplicateActiveSku_throwsConflict() {
            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivity duplicate = new SeckillActivity();
            duplicate.setName("Second sale for same SKU");
            duplicate.setSkuId(100L);

            assertThatThrownBy(() -> seckillService.create(duplicate))
                    .isInstanceOf(ConflictException.class)
                    .hasFieldOrPropertyWithValue("code", "CONFLICT");
            verify(seckillRepository, never()).save(any(SeckillActivity.class));
        }

        @Test
        @DisplayName("create: rejects invalid time range — endTime not after startTime")
        void testCreate_invalidTimeRange() {
            activity.setStartTime(LocalDateTime.now());
            activity.setEndTime(LocalDateTime.now().minusHours(1));

            assertThatThrownBy(() -> seckillService.create(activity))
                    .isInstanceOf(ValidationException.class)
                    .hasMessageContaining("End time must be after start time");
        }

        @Test
        @DisplayName("create: accepts null time range without validation")
        void testCreate_nullTimeRange() {
            activity.setStartTime(null);
            activity.setEndTime(null);

            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            // Should not throw — the null guard in create means the validation is skipped
            SeckillActivityDto result = seckillService.create(activity);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("create: accepts null endTime with non-null startTime")
        void testCreate_nullEndTime() {
            activity.setStartTime(LocalDateTime.now());
            activity.setEndTime(null);

            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            SeckillActivityDto result = seckillService.create(activity);
            assertThat(result).isNotNull();
        }
    }

    // -----------------------------------------------------------------------
    // validateSeckill tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("validateSeckill")
    class ValidateSeckill {

        @Test
        @DisplayName("validateSeckill: returns activity when within time window and stock available")
        void testValidateSeckill_active() {
            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1);

            assertThat(result).isNotNull();
            assertThat(result.getSkuId()).isEqualTo(100L);
            assertThat(result.getStatus()).isEqualTo("ACTIVE");
        }

        @Test
        @DisplayName("validateSeckill: throws when no active seckill for SKU")
        void testValidateSeckill_notFound() {
            when(seckillRepository.findBySkuIdAndStatus(999L, "ACTIVE"))
                    .thenReturn(Optional.empty());

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 999L, 1))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .hasMessageContaining("SeckillActivity");
        }

        @Test
        @DisplayName("validateSeckill: throws when seckill has not started")
        void testValidateSeckill_notStarted() {
            activity.setStartTime(LocalDateTime.now().plusHours(2));
            activity.setEndTime(LocalDateTime.now().plusHours(4));

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 1))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("not started");
        }

        @Test
        @DisplayName("validateSeckill: throws when seckill has already ended")
        void testValidateSeckill_ended() {
            activity.setStartTime(LocalDateTime.now().minusHours(4));
            activity.setEndTime(LocalDateTime.now().minusHours(2));

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 1))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("already ended");
        }

        @Test
        @DisplayName("validateSeckill: throws when stock is sold out")
        void testValidateSeckill_soldOut() {
            activity.setStockQuantity(50);
            activity.setSoldQuantity(50); // sold = stock

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 1))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("exhausted");
        }

        @Test
        @DisplayName("validateSeckill: throws when stock is negative (sold > stock)")
        void testValidateSeckill_overSold() {
            activity.setStockQuantity(50);
            activity.setSoldQuantity(60);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 1))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("exhausted");
        }

        @Test
        @DisplayName("validateSeckill: handles null stockQuantity as 0 stock")
        void testValidateSeckill_nullStock() {
            activity.setStockQuantity(null);
            activity.setSoldQuantity(0);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 1))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("exhausted");
        }

        @Test
        @DisplayName("validateSeckill: handles null soldQuantity as 0 sold")
        void testValidateSeckill_nullSold() {
            activity.setStockQuantity(10);
            activity.setSoldQuantity(null);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("validateSeckill: handles null time bounds — passes validation")
        void testValidateSeckill_nullTimes() {
            activity.setStartTime(null);
            activity.setEndTime(null);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            // Both null — time checks are skipped
            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("validateSeckill: passes with exactly enough remaining stock for the requested quantity")
        void testValidateSeckill_lastStock() {
            activity.setStockQuantity(10);
            activity.setSoldQuantity(9); // 1 left
            activity.setPerUserLimit(null); // isolate this test from the per-user-limit check

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("validateSeckill: throws SECKILL_SOLD_OUT when requested quantity exceeds remaining stock")
        void testValidateSeckill_quantityExceedsRemainingStock() {
            activity.setStockQuantity(10);
            activity.setSoldQuantity(8); // 2 left
            activity.setPerUserLimit(null); // isolate this test from the per-user-limit check

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            // Only 2 remain, but 3 are requested.
            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 3))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("exhausted");
        }

        @Test
        @DisplayName("validateSeckill: treats a null quantity as 1")
        void testValidateSeckill_nullQuantity_treatedAsOne() {
            activity.setStockQuantity(1);
            activity.setSoldQuantity(0);
            activity.setPerUserLimit(null);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, null);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("validateSeckill: passes when the user has not yet reached their per-user limit")
        void testValidateSeckill_underPerUserLimit_passes() {
            activity.setPerUserLimit(3);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));
            when(purchaseRecordRepository.findByActivityIdAndUserId(1L, USER_ID))
                    .thenReturn(List.of(purchaseOf(2)));

            // Already purchased 2, requesting 1 more — total 3, exactly at the limit.
            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1);
            assertThat(result).isNotNull();
        }

        @Test
        @DisplayName("validateSeckill: throws SECKILL_LIMIT_EXCEEDED when the per-user limit would be exceeded")
        void testValidateSeckill_exceedsPerUserLimit_throws() {
            activity.setPerUserLimit(1);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));
            when(purchaseRecordRepository.findByActivityIdAndUserId(1L, USER_ID))
                    .thenReturn(List.of(purchaseOf(1)));

            // Already purchased 1 (the full limit); requesting 1 more should be rejected.
            BusinessException ex = catchThrowableOfType(
                    () -> seckillService.validateSeckill(USER_ID, 100L, 1),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("SECKILL_LIMIT_EXCEEDED");
        }

        @Test
        @DisplayName("validateSeckill: sums multiple prior purchase records against the per-user limit")
        void testValidateSeckill_sumsMultiplePriorPurchases() {
            activity.setPerUserLimit(5);

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));
            when(purchaseRecordRepository.findByActivityIdAndUserId(1L, USER_ID))
                    .thenReturn(List.of(purchaseOf(2), purchaseOf(2)));

            // 2 + 2 = 4 already purchased; requesting 2 more would total 6 > limit 5.
            assertThatThrownBy(() -> seckillService.validateSeckill(USER_ID, 100L, 2))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("per-user purchase limit");
        }

        @Test
        @DisplayName("validateSeckill: skips the per-user-limit check when perUserLimit is not configured")
        void testValidateSeckill_noPerUserLimitConfigured_skipsCheck() {
            activity.setPerUserLimit(null);
            activity.setStockQuantity(2000); // large enough that only the limit check (not stock) is exercised

            when(seckillRepository.findBySkuIdAndStatus(100L, "ACTIVE"))
                    .thenReturn(Optional.of(activity));

            SeckillActivityDto result = seckillService.validateSeckill(USER_ID, 100L, 1000);
            assertThat(result).isNotNull();
            verify(purchaseRecordRepository, never()).findByActivityIdAndUserId(any(), any());
        }

        private SeckillPurchaseRecord purchaseOf(int quantity) {
            SeckillPurchaseRecord record = new SeckillPurchaseRecord();
            record.setActivityId(1L);
            record.setUserId(USER_ID);
            record.setQuantity(quantity);
            return record;
        }
    }

    // -----------------------------------------------------------------------
    // recordPurchase tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("recordPurchase")
    class RecordPurchase {

        @Test
        @DisplayName("recordPurchase: increments soldQuantity by the purchased quantity")
        void testRecordPurchase_incrementsSold() {
            activity.setSoldQuantity(5);
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.recordPurchase(1L, USER_ID, 3, ORDER_ID);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(8);
        }

        @Test
        @DisplayName("recordPurchase: handles null soldQuantity — starts from the purchased quantity")
        void testRecordPurchase_nullSold() {
            activity.setSoldQuantity(null);
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.recordPurchase(1L, USER_ID, 1, ORDER_ID);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(1);
        }

        @Test
        @DisplayName("recordPurchase: treats a null quantity as 1")
        void testRecordPurchase_nullQuantity_treatedAsOne() {
            activity.setSoldQuantity(5);
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.recordPurchase(1L, USER_ID, null, ORDER_ID);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(6);
        }

        @Test
        @DisplayName("recordPurchase: throws when activity not found")
        void testRecordPurchase_notFound() {
            when(seckillRepository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> seckillService.recordPurchase(999L, USER_ID, 1, ORDER_ID))
                    .isInstanceOf(ResourceNotFoundException.class);
        }

        @Test
        @DisplayName("recordPurchase: persists a purchase record for future per-user-limit checks")
        void testRecordPurchase_persistsPurchaseRecord() {
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.recordPurchase(1L, USER_ID, 2, ORDER_ID);

            verify(purchaseRecordRepository).save(purchaseRecordCaptor.capture());
            SeckillPurchaseRecord saved = purchaseRecordCaptor.getValue();
            assertThat(saved.getActivityId()).isEqualTo(1L);
            assertThat(saved.getUserId()).isEqualTo(USER_ID);
            assertThat(saved.getOrderId()).isEqualTo(ORDER_ID);
            assertThat(saved.getQuantity()).isEqualTo(2);
        }
    }

    // -----------------------------------------------------------------------
    // releaseForOrder tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("releaseForOrder")
    class ReleaseForOrder {

        private SeckillPurchaseRecord record;

        @BeforeEach
        void setUp() {
            record = new SeckillPurchaseRecord();
            record.setActivityId(1L);
            record.setUserId(USER_ID);
            record.setOrderId(ORDER_ID);
            record.setQuantity(2);
        }

        @Test
        @DisplayName("releaseForOrder: restores soldQuantity and deletes the purchase record")
        void testReleaseForOrder_restoresStockAndDeletesRecord() {
            activity.setSoldQuantity(5);
            when(purchaseRecordRepository.findByOrderId(ORDER_ID)).thenReturn(List.of(record));
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.releaseForOrder(ORDER_ID);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(3);
            verify(purchaseRecordRepository).delete(record);
        }

        @Test
        @DisplayName("releaseForOrder: floors soldQuantity at 0 instead of going negative")
        void testReleaseForOrder_floorsSoldAtZero() {
            activity.setSoldQuantity(1);
            when(purchaseRecordRepository.findByOrderId(ORDER_ID)).thenReturn(List.of(record));
            when(seckillRepository.findById(1L)).thenReturn(Optional.of(activity));
            when(seckillRepository.save(any(SeckillActivity.class))).thenReturn(activity);

            seckillService.releaseForOrder(ORDER_ID);

            verify(seckillRepository).save(activityCaptor.capture());
            assertThat(activityCaptor.getValue().getSoldQuantity()).isEqualTo(0);
        }

        @Test
        @DisplayName("releaseForOrder: is a no-op for an order without seckill purchases")
        void testReleaseForOrder_noRecords_noop() {
            when(purchaseRecordRepository.findByOrderId(ORDER_ID)).thenReturn(List.of());

            seckillService.releaseForOrder(ORDER_ID);

            verify(seckillRepository, never()).save(any(SeckillActivity.class));
            verify(purchaseRecordRepository, never()).delete(any(SeckillPurchaseRecord.class));
        }

        @Test
        @DisplayName("releaseForOrder: still deletes the record when the activity no longer exists")
        void testReleaseForOrder_activityGone_stillDeletesRecord() {
            when(purchaseRecordRepository.findByOrderId(ORDER_ID)).thenReturn(List.of(record));
            when(seckillRepository.findById(1L)).thenReturn(Optional.empty());

            seckillService.releaseForOrder(ORDER_ID);

            verify(seckillRepository, never()).save(any(SeckillActivity.class));
            verify(purchaseRecordRepository).delete(record);
        }
    }
}
