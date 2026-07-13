package com.ecommerce.loyalty.dto;

import java.math.BigDecimal;

/**
 * Response DTO for GET /api/v1/loyalty/member-level.
 */
public class MemberLevelResponse {

    private String level;
    private String levelName;
    private double multiplier;
    private BigDecimal annualConsumption;
    private String nextLevelCondition;

    /**
     * How far this account still is from the next membership tier, expressed
     * in points. design-docs/12 §5 sets the tier thresholds in annual
     * consumption yuan and §2 sets the earn rate at 1 point per yuan, so the
     * remaining-consumption gap and the remaining-points gap are the same
     * number: {@code nextTierThreshold - annualConsumption}, floored at 0.
     * 0 for PLATINUM (already the highest tier). Read by the frozen
     * black-box fixture under exactly this field name (additive — existing
     * fields are untouched).
     */
    private int pointsToNextLevel;

    public MemberLevelResponse() {
    }

    public String getLevel() {
        return level;
    }

    public void setLevel(String level) {
        this.level = level;
    }

    public String getLevelName() {
        return levelName;
    }

    public void setLevelName(String levelName) {
        this.levelName = levelName;
    }

    public double getMultiplier() {
        return multiplier;
    }

    public void setMultiplier(double multiplier) {
        this.multiplier = multiplier;
    }

    public BigDecimal getAnnualConsumption() {
        return annualConsumption;
    }

    public void setAnnualConsumption(BigDecimal annualConsumption) {
        this.annualConsumption = annualConsumption;
    }

    public String getNextLevelCondition() {
        return nextLevelCondition;
    }

    public void setNextLevelCondition(String nextLevelCondition) {
        this.nextLevelCondition = nextLevelCondition;
    }

    public int getPointsToNextLevel() {
        return pointsToNextLevel;
    }

    public void setPointsToNextLevel(int pointsToNextLevel) {
        this.pointsToNextLevel = pointsToNextLevel;
    }
}
