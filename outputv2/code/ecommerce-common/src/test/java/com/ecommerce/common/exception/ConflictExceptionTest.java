package com.ecommerce.common.exception;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ConflictExceptionTest {

    @Test
    void singleArgConstructor_defaultsCodeToConflict() {
        ConflictException ex = new ConflictException("duplicate");
        assertEquals("CONFLICT", ex.getCode());
        assertEquals("duplicate", ex.getMessage());
    }

    @Test
    void twoArgConstructor_usesGivenCode() {
        ConflictException ex = new ConflictException("ORDER_STATUS_CONFLICT", "wrong state");
        assertEquals("ORDER_STATUS_CONFLICT", ex.getCode());
        assertEquals("wrong state", ex.getMessage());
    }
}
