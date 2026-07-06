package com.ecommerce.loyalty.entity;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

/**
 * Unit tests for the {@link MemberLevel} enum, including verification
 * of actual multiplier values.
 *
 * <p>design-docs/12-积分与会员服务设计.md §5 mandates GOLD = 1.2 (distinct
 * from SILVER's 1.1); the implementation previously duplicated SILVER's
 * 1.1 value for GOLD.
 */
class MemberLevelTest {

    /**
     * Verifies the GOLD multiplier matches design-docs/12 §5 (1.2), and is
     * no longer accidentally equal to SILVER's 1.1.
     */
    @Test
    void testGoldMultiplier_returnsActualValue() {
        double actual = MemberLevel.GOLD.getMultiplier();

        assertEquals(1.2, actual, 0.0001,
                "GOLD multiplier must be 1.2 per design-docs/12 §5");

        assertNotEquals(1.1, actual, 0.0001,
                "GOLD level multiplier must not collide with SILVER's 1.1");
    }

    @Test
    void testAllLevels_haveCorrectMultipliers() {
        assertEquals(1.0, MemberLevel.NORMAL.getMultiplier(), 0.0001,
                "NORMAL level multiplier should be 1.0");
        assertEquals(1.1, MemberLevel.SILVER.getMultiplier(), 0.0001,
                "SILVER level multiplier should be 1.1");
        assertEquals(1.2, MemberLevel.GOLD.getMultiplier(), 0.0001,
                "GOLD level multiplier should be 1.2");
        assertEquals(1.5, MemberLevel.PLATINUM.getMultiplier(), 0.0001,
                "PLATINUM level multiplier should be 1.5");
    }
}
