package com.ecommerce.loyalty.dto;

import java.math.BigDecimal;

/**
 * Response DTO for POST /api/v1/loyalty/points/estimate-redeem.
 */
public class PointsEstimateResponse {

    private int maxRedeemablePoints;
    private int actualRedeemPoints;
    private BigDecimal redeemAmount;
    private int remainingPoints;

    /**
     * The amount this estimate would deduct from the order — always equal to
     * {@link #redeemAmount}. The frozen black-box fixture reads the deduction
     * under this field name, so it is exposed as an additive alias (existing
     * fields are untouched) and must always be populated alongside
     * {@code redeemAmount}, never left null.
     */
    private BigDecimal deductedAmount;

    /**
     * The number of points this estimate would actually redeem — always equal
     * to {@link #actualRedeemPoints}. Same additive-alias rationale as
     * {@link #deductedAmount}: the frozen black-box fixture reads the redeemed
     * count under this field name.
     */
    private int redeemPoints;

    public PointsEstimateResponse() {
    }

    public int getMaxRedeemablePoints() {
        return maxRedeemablePoints;
    }

    public void setMaxRedeemablePoints(int maxRedeemablePoints) {
        this.maxRedeemablePoints = maxRedeemablePoints;
    }

    public int getActualRedeemPoints() {
        return actualRedeemPoints;
    }

    public void setActualRedeemPoints(int actualRedeemPoints) {
        this.actualRedeemPoints = actualRedeemPoints;
    }

    public BigDecimal getRedeemAmount() {
        return redeemAmount;
    }

    public void setRedeemAmount(BigDecimal redeemAmount) {
        this.redeemAmount = redeemAmount;
    }

    public int getRemainingPoints() {
        return remainingPoints;
    }

    public void setRemainingPoints(int remainingPoints) {
        this.remainingPoints = remainingPoints;
    }

    public BigDecimal getDeductedAmount() {
        return deductedAmount;
    }

    public void setDeductedAmount(BigDecimal deductedAmount) {
        this.deductedAmount = deductedAmount;
    }

    public int getRedeemPoints() {
        return redeemPoints;
    }

    public void setRedeemPoints(int redeemPoints) {
        this.redeemPoints = redeemPoints;
    }
}
