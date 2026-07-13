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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * Service for managing and validating seckill (flash-sale) activities.
 */
@Service
public class SeckillService {

    private final SeckillRepository seckillRepository;
    private final SeckillPurchaseRecordRepository purchaseRecordRepository;

    public SeckillService(SeckillRepository seckillRepository,
                           SeckillPurchaseRecordRepository purchaseRecordRepository) {
        this.seckillRepository = seckillRepository;
        this.purchaseRecordRepository = purchaseRecordRepository;
    }

    /**
     * Create a new seckill activity. ADMIN only.
     *
     * <p>At most one ACTIVE activity may exist per SKU: the whole seckill lookup
     * path ({@link SeckillRepository#findBySkuIdAndStatus} returning an
     * {@code Optional}) is built on that invariant, so a duplicate would turn
     * every order probing this SKU into a non-unique-result 500. A duplicate
     * creation attempt is therefore rejected with 409 CONFLICT.
     */
    @Transactional
    public SeckillActivityDto create(SeckillActivity activity) {
        if (activity.getStartTime() != null && activity.getEndTime() != null
                && !activity.getEndTime().isAfter(activity.getStartTime())) {
            throw new ValidationException("endTime", "End time must be after start time");
        }
        if (activity.getSkuId() != null
                && seckillRepository.findBySkuIdAndStatus(activity.getSkuId(), "ACTIVE").isPresent()) {
            throw new ConflictException("同 SKU 已存在进行中的秒杀活动");
        }
        activity.setSoldQuantity(0);
        activity.setStatus("ACTIVE");
        return toDto(seckillRepository.save(activity));
    }

    /**
     * Validate whether a seckill purchase is allowed, per design-docs/10 §4:
     *
     * <p>Checks:
     * <ol>
     *   <li>Activity is in progress (within time window)</li>
     *   <li>SKU is part of the activity</li>
     *   <li>User has not exceeded the per-user purchase limit</li>
     *   <li>Seckill stock is sufficient for the requested quantity</li>
     * </ol>
     *
     * <p>Rule 5 ("seckill price does not participate in ordinary full-reduction")
     * is enforced by the order module when it composes the order total, since
     * only it knows the full set of line items in the order.
     *
     * @param userId   the purchasing user, used for the per-user limit check
     * @param skuId    the SKU being purchased
     * @param quantity the quantity requested; treated as 1 if null
     * @return the matching active activity as a {@link SeckillActivityDto},
     *         for its seckill price (a JPA entity must never cross the module
     *         boundary to the order-side caller — design-docs/02 §3 rule 3)
     */
    // The order-creation flow calls this as a probe to decide whether a SKU is on
    // an active seckill, treating "no active seckill for this SKU"
    // (ResourceNotFoundException) as a normal, non-error signal and falling back to
    // the list price. Since this method participates in the caller's transaction,
    // a plain throw would mark that transaction rollback-only — so the caller's
    // legitimate swallow of the signal would still make the whole order fail at
    // commit (UnexpectedRollbackException). noRollbackFor keeps the benign
    // not-found case from poisoning the caller's transaction, while genuine seckill
    // failures (SECKILL_SOLD_OUT / SECKILL_ENDED / ... , thrown as BusinessException)
    // still propagate and roll back as before.
    @Transactional(readOnly = true, noRollbackFor = ResourceNotFoundException.class)
    public SeckillActivityDto validateSeckill(Long userId, Long skuId, Integer quantity) {
        SeckillActivity activity = seckillRepository.findBySkuIdAndStatus(skuId, "ACTIVE")
                .orElseThrow(() -> new ResourceNotFoundException("SeckillActivity for SKU", skuId));

        int purchaseQuantity = quantity != null ? quantity : 1;

        // Check time window
        LocalDateTime now = SystemClockService.now();
        if (activity.getStartTime() != null && now.isBefore(activity.getStartTime())) {
            throw new BusinessException("SECKILL_NOT_STARTED",
                    "Seckill activity has not started yet");
        }
        if (activity.getEndTime() != null && now.isAfter(activity.getEndTime())) {
            throw new BusinessException("SECKILL_ENDED",
                    "Seckill activity has already ended");
        }

        // Check per-user purchase limit
        if (activity.getPerUserLimit() != null && userId != null) {
            int alreadyPurchased = purchaseRecordRepository
                    .findByActivityIdAndUserId(activity.getId(), userId)
                    .stream()
                    .mapToInt(record -> record.getQuantity() != null ? record.getQuantity() : 0)
                    .sum();
            if (alreadyPurchased + purchaseQuantity > activity.getPerUserLimit()) {
                throw new BusinessException("SECKILL_LIMIT_EXCEEDED",
                        "Exceeds the per-user purchase limit for this seckill activity");
            }
        }

        // Check stock
        int availableStock = (activity.getStockQuantity() != null ? activity.getStockQuantity() : 0)
                - (activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0);
        if (availableStock < purchaseQuantity) {
            throw new BusinessException("SECKILL_SOLD_OUT",
                    "Seckill stock has been exhausted");
        }

        return toDto(activity);
    }

    /**
     * Record a successful seckill purchase: decrements remaining stock and
     * records the user's purchased quantity for future per-user-limit checks.
     *
     * @param activityId the seckill activity purchased from
     * @param userId     the purchasing user
     * @param quantity   the quantity purchased; treated as 1 if null
     * @param orderId    the order that consumed this allocation, so it can be
     *                   given back if that order is cancelled
     */
    @Transactional
    public void recordPurchase(Long activityId, Long userId, Integer quantity, Long orderId) {
        SeckillActivity activity = seckillRepository.findById(activityId)
                .orElseThrow(() -> new ResourceNotFoundException("SeckillActivity", activityId));

        int purchaseQuantity = quantity != null ? quantity : 1;
        int sold = activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0;
        activity.setSoldQuantity(sold + purchaseQuantity);
        seckillRepository.save(activity);

        SeckillPurchaseRecord record = new SeckillPurchaseRecord();
        record.setActivityId(activityId);
        record.setUserId(userId);
        record.setOrderId(orderId);
        record.setQuantity(purchaseQuantity);
        purchaseRecordRepository.save(record);
    }

    /**
     * Give back the seckill allocation consumed by a cancelled order: for each
     * purchase record of that order, the activity's {@code soldQuantity} is
     * restored (floored at 0) and the record itself is deleted, so both the
     * activity stock and the user's per-user-limit headroom are returned.
     * The inverse of {@link #recordPurchase}, called by the order module on
     * the successful-cancellation paths.
     *
     * <p>Deliberately a no-op for orders without seckill items, and never
     * throws in normal operation — a release failure must not block the
     * cancellation itself (a vanished activity just skips the stock
     * restoration and still removes the stale record).
     */
    @Transactional
    public void releaseForOrder(Long orderId) {
        if (orderId == null) {
            return;
        }
        for (SeckillPurchaseRecord record : purchaseRecordRepository.findByOrderId(orderId)) {
            seckillRepository.findById(record.getActivityId()).ifPresent(activity -> {
                int sold = activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0;
                int quantity = record.getQuantity() != null ? record.getQuantity() : 0;
                activity.setSoldQuantity(Math.max(0, sold - quantity));
                seckillRepository.save(activity);
            });
            purchaseRecordRepository.delete(record);
        }
    }

    /**
     * Map the JPA entity to its boundary DTO, field for field. The single
     * conversion point for everything this service returns across the module
     * boundary (REST response body, order-side seckill probe) — the entity
     * itself must never leave the promotion module (design-docs/02 §3 rule 3).
     */
    private SeckillActivityDto toDto(SeckillActivity activity) {
        SeckillActivityDto dto = new SeckillActivityDto();
        dto.setId(activity.getId());
        dto.setCreatedAt(activity.getCreatedAt());
        dto.setUpdatedAt(activity.getUpdatedAt());
        dto.setName(activity.getName());
        dto.setSkuId(activity.getSkuId());
        dto.setSeckillPrice(activity.getSeckillPrice());
        dto.setStockQuantity(activity.getStockQuantity());
        dto.setSoldQuantity(activity.getSoldQuantity());
        dto.setPerUserLimit(activity.getPerUserLimit());
        dto.setStartTime(activity.getStartTime());
        dto.setEndTime(activity.getEndTime());
        dto.setStatus(activity.getStatus());
        return dto;
    }
}
