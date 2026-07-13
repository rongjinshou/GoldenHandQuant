package com.ecommerce.promotion.entity;

import com.ecommerce.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

/**
 * Records the quantity a single user has purchased within a seckill
 * activity, used to enforce {@link SeckillActivity#getPerUserLimit()}.
 */
@Entity
@Table(name = "seckill_purchase_record")
public class SeckillPurchaseRecord extends BaseEntity {

    @Column(name = "activity_id", nullable = false)
    private Long activityId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    /**
     * The order that consumed this seckill allocation. Used to give the
     * allocation back (restore activity stock and per-user limit headroom)
     * when that order is cancelled.
     */
    @Column(name = "order_id")
    private Long orderId;

    @Column(nullable = false)
    private Integer quantity;

    // ---- constructors ----

    public SeckillPurchaseRecord() {
    }

    // ---- getters and setters ----

    public Long getActivityId() {
        return activityId;
    }

    public void setActivityId(Long activityId) {
        this.activityId = activityId;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public Long getOrderId() {
        return orderId;
    }

    public void setOrderId(Long orderId) {
        this.orderId = orderId;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }
}
