package com.ecommerce.cart.dto;

import com.ecommerce.promotion.dto.PromotionCalculateResponse;

import java.math.BigDecimal;
import java.util.List;

/**
 * Response DTO for cart price estimation.
 */
public class CartEstimateResponse {

    private BigDecimal itemTotal;
    private BigDecimal shippingFee;
    private BigDecimal packagingFee;
    private BigDecimal discountAmount;
    private BigDecimal pointsDeductionAmount;
    private BigDecimal payableAmount;
    private List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons;

    public CartEstimateResponse() {
    }

    public BigDecimal getItemTotal() {
        return itemTotal;
    }

    public void setItemTotal(BigDecimal itemTotal) {
        this.itemTotal = itemTotal;
    }

    public BigDecimal getShippingFee() {
        return shippingFee;
    }

    public void setShippingFee(BigDecimal shippingFee) {
        this.shippingFee = shippingFee;
    }

    public BigDecimal getPackagingFee() {
        return packagingFee;
    }

    public void setPackagingFee(BigDecimal packagingFee) {
        this.packagingFee = packagingFee;
    }

    public BigDecimal getDiscountAmount() {
        return discountAmount;
    }

    public void setDiscountAmount(BigDecimal discountAmount) {
        this.discountAmount = discountAmount;
    }

    public BigDecimal getPointsDeductionAmount() {
        return pointsDeductionAmount;
    }

    public void setPointsDeductionAmount(BigDecimal pointsDeductionAmount) {
        this.pointsDeductionAmount = pointsDeductionAmount;
    }

    public BigDecimal getPayableAmount() {
        return payableAmount;
    }

    public void setPayableAmount(BigDecimal payableAmount) {
        this.payableAmount = payableAmount;
    }

    public List<PromotionCalculateResponse.ApplicableCoupon> getApplicableCoupons() {
        return applicableCoupons;
    }

    public void setApplicableCoupons(List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons) {
        this.applicableCoupons = applicableCoupons;
    }
}
