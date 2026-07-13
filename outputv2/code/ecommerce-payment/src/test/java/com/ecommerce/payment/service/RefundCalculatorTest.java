package com.ecommerce.payment.service;

import com.ecommerce.payment.config.PaymentConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Tests for {@link RefundCalculator}.
 *
 * <p>Per design-docs/09 §5, {@code refund = paidAmount * (1 - feeRate)},
 * with no extra flat fee deducted. The default fee rate is 2%, so the
 * default refund factor is 0.98.
 */
class RefundCalculatorTest {

    private RefundCalculator calculator;

    @BeforeEach
    void setUp() {
        PaymentConfig config = new PaymentConfig();
        // feeRate defaults to 0.02 (2%), so refund factor is 0.98
        calculator = new RefundCalculator(config);
    }

    // ---- testCalculate_standardRefund_appliesFee ----

    @Test
    @DisplayName("standard refund = paid * 0.98, no flat fee deducted")
    void testCalculate_standardRefund_appliesFee() {
        // 100.00 * 0.98 = 98.00
        BigDecimal result = calculator.calculate(new BigDecimal("100.00"));

        assertEquals(new BigDecimal("98.00"), result,
                "refund = paid * 0.98, so 100 * 0.98 = 98.00");
    }

    // ---- testCalculate_defaultFeeRate_noFlatFeeDeducted ----

    @Test
    @DisplayName("calculate() with the default fee rate deducts no flat fee")
    void calculate_defaultFeeRate_noFlatFeeDeducted() {
        BigDecimal refund = calculator.calculate(new BigDecimal("100.00"));

        assertEquals(0, new BigDecimal("98.00").compareTo(refund));
    }

    // ---- testCalculate_largeAmount_reflectsFeeOnly ----

    @Test
    @DisplayName("large amount refund reflects only the 2% fee")
    void testCalculate_largeAmount_reflectsFeeOnly() {
        // 1000.00 * 0.98 = 980.00
        BigDecimal result = calculator.calculate(new BigDecimal("1000.00"));

        assertEquals(new BigDecimal("980.00"), result,
                "1000 * 0.98 = 980.00");
    }

    // ---- testCalculate_zeroAmount_returnsZero ----

    @Test
    @DisplayName("zero paid amount returns zero; small amounts scale linearly with no flat deduction")
    void testCalculate_zeroAmount_returnsZero() {
        // Given: paid amount is 0 — the null/zero guard returns BigDecimal.ZERO
        BigDecimal zeroResult = calculator.calculate(BigDecimal.ZERO);
        assertEquals(BigDecimal.ZERO, zeroResult,
                "Zero paid amount returns ZERO due to guard clause");

        // A small amount should scale by the fee factor alone, with no flat
        // deduction: 2.00 * 0.98 = 1.96 (NOT 0.96, which the old buggy
        // -1.00 subtraction would have produced).
        BigDecimal tinyResult = calculator.calculate(new BigDecimal("2.00"));
        assertEquals(new BigDecimal("1.96"), tinyResult,
                "2.00 * 0.98 = 1.96");
    }
}
