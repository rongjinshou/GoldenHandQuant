package com.ecommerce.promotion.dto;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Boundary DTO for a seckill activity.
 *
 * <p>design-docs/02 §3 rule 3: data crossing a module boundary must be a DTO,
 * never a JPA entity. This class is what {@code SeckillService} hands to the
 * REST layer and to other modules (the order module's seckill probe) instead
 * of the {@code SeckillActivity} entity itself.
 *
 * <p>Field names, types and declaration order deliberately mirror the JSON
 * shape the entity used to serialize (BaseEntity audit fields first, then the
 * activity fields), so the frozen REST response of
 * {@code POST /api/v1/admin/promotions/seckill} is unchanged field-for-field.
 */
public class SeckillActivityDto {

    private Long id;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private String name;
    private Long skuId;
    private BigDecimal seckillPrice;
    private Integer stockQuantity;
    private Integer soldQuantity;
    private Integer perUserLimit;
    private LocalDateTime startTime;
    private LocalDateTime endTime;

    /**
     * Activity status: ACTIVE, INACTIVE, or FINISHED.
     */
    private String status;

    public SeckillActivityDto() {
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public Long getSkuId() {
        return skuId;
    }

    public void setSkuId(Long skuId) {
        this.skuId = skuId;
    }

    public BigDecimal getSeckillPrice() {
        return seckillPrice;
    }

    public void setSeckillPrice(BigDecimal seckillPrice) {
        this.seckillPrice = seckillPrice;
    }

    public Integer getStockQuantity() {
        return stockQuantity;
    }

    public void setStockQuantity(Integer stockQuantity) {
        this.stockQuantity = stockQuantity;
    }

    public Integer getSoldQuantity() {
        return soldQuantity;
    }

    public void setSoldQuantity(Integer soldQuantity) {
        this.soldQuantity = soldQuantity;
    }

    public Integer getPerUserLimit() {
        return perUserLimit;
    }

    public void setPerUserLimit(Integer perUserLimit) {
        this.perUserLimit = perUserLimit;
    }

    public LocalDateTime getStartTime() {
        return startTime;
    }

    public void setStartTime(LocalDateTime startTime) {
        this.startTime = startTime;
    }

    public LocalDateTime getEndTime() {
        return endTime;
    }

    public void setEndTime(LocalDateTime endTime) {
        this.endTime = endTime;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
