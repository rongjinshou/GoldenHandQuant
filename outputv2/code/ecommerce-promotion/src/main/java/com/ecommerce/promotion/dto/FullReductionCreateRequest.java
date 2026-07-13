package com.ecommerce.promotion.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * DTO for creating a full-reduction activity (admin).
 *
 * <p>The frozen black-box fixture (PromotionFixture#createFullReduction) posts the
 * short field names {@code threshold}/{@code reduction}, so both spellings are
 * accepted on input via {@link JsonAlias}; serialized output keeps the long names.
 */
public class FullReductionCreateRequest {

    @NotBlank
    private String name;

    @NotNull
    @JsonAlias("threshold")
    private BigDecimal thresholdAmount;

    @NotNull
    @JsonAlias("reduction")
    private BigDecimal reductionAmount;

    private LocalDateTime startTime;

    private LocalDateTime endTime;

    /**
     * ALL or SPECIFIC.
     */
    private String productScope;

    private List<Long> applicableCategoryIds;

    // ---- getters and setters ----

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public BigDecimal getThresholdAmount() {
        return thresholdAmount;
    }

    public void setThresholdAmount(BigDecimal thresholdAmount) {
        this.thresholdAmount = thresholdAmount;
    }

    public BigDecimal getReductionAmount() {
        return reductionAmount;
    }

    public void setReductionAmount(BigDecimal reductionAmount) {
        this.reductionAmount = reductionAmount;
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

    public String getProductScope() {
        return productScope;
    }

    public void setProductScope(String productScope) {
        this.productScope = productScope;
    }

    public List<Long> getApplicableCategoryIds() {
        return applicableCategoryIds;
    }

    public void setApplicableCategoryIds(List<Long> applicableCategoryIds) {
        this.applicableCategoryIds = applicableCategoryIds;
    }
}
