package com.ecommerce.promotion.repository;

import com.ecommerce.promotion.entity.SeckillPurchaseRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Repository for {@link SeckillPurchaseRecord} entities.
 */
@Repository
public interface SeckillPurchaseRecordRepository extends JpaRepository<SeckillPurchaseRecord, Long> {

    /**
     * Find all purchase records for a given user within a given activity,
     * used to sum up how much of the per-user limit has already been used.
     */
    List<SeckillPurchaseRecord> findByActivityIdAndUserId(Long activityId, Long userId);
}
