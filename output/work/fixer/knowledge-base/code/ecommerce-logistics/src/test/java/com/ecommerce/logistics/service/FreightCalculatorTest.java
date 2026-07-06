package com.ecommerce.logistics.service;

import com.ecommerce.logistics.cache.FreightTemplateCacheManager;
import com.ecommerce.logistics.entity.FreightTemplate;
import com.ecommerce.logistics.repository.FreightTemplateRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link FreightCalculator}.
 *
 * <p>Verifies the freight calculation logic, the 30-minute templateId-keyed cache
 * (design-docs/11 section 4), and province/weight rule parsing.
 */
@ExtendWith(MockitoExtension.class)
class FreightCalculatorTest {

    @Mock
    private FreightTemplateRepository freightTemplateRepository;
    @Mock
    private FreightTemplateCacheManager freightTemplateCacheManager;

    private FreightCalculator calculator;

    @BeforeEach
    void setUp() {
        lenient().when(freightTemplateRepository.findAll()).thenReturn(Collections.emptyList());
        // Simulate an always-cold cache by default; individual tests override this to prove hits.
        lenient().when(freightTemplateCacheManager.get(any())).thenReturn(null);
        calculator = new FreightCalculator(freightTemplateRepository, freightTemplateCacheManager,
                new ObjectMapper());
    }

    /**
     * itemTotal=199.00 qualifies for free shipping.
     * Verifies threshold boundary behavior.
     */
    @Test
    void testCalculate_exactly199_freeShipping() {
        BigDecimal result = calculator.calculateFreight(new BigDecimal("199.00"));
        assertEquals(BigDecimal.ZERO, result,
                "itemTotal=199.00 boundary result");
    }

    @Test
    void testCalculate_over199_freeShipping() {
        BigDecimal result = calculator.calculateFreight(new BigDecimal("200.00"));
        assertEquals(BigDecimal.ZERO, result);
    }

    @Test
    void testCalculate_below199_chargesShipping() {
        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"));
        assertEquals(new BigDecimal("8.00"), result);
    }

    @Test
    void testCalculate_zeroAmount_chargesShipping() {
        BigDecimal result = calculator.calculateFreight(BigDecimal.ZERO);
        assertEquals(new BigDecimal("8.00"), result);
    }

    @Test
    void testCalculate_nullAmount_chargesShipping() {
        BigDecimal result = calculator.calculateFreight(null);
        assertEquals(new BigDecimal("8.00"), result);
    }

    @Test
    void testCalculate_negativeAmount_chargesShipping() {
        BigDecimal result = calculator.calculateFreight(new BigDecimal("-10.00"));
        assertEquals(new BigDecimal("8.00"), result);
    }

    @Test
    void testCalculate_justAboveThreshold_freeShipping() {
        BigDecimal result = calculator.calculateFreight(new BigDecimal("199.01"));
        assertEquals(BigDecimal.ZERO, result);
    }

    @Test
    void testCalculate_withActiveTemplate_overridesThreshold() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setName("Express");
        template.setDefaultFreight(new BigDecimal("15.00"));
        template.setFreeShippingThreshold(new BigDecimal("299.00"));

        when(freightTemplateRepository.findAll()).thenReturn(Collections.singletonList(template));

        // 250.00 < 299.00 threshold, so freight is charged
        BigDecimal result = calculator.calculateFreight(new BigDecimal("250.00"));
        assertEquals(new BigDecimal("15.00"), result);

        // 299.00 reaches the threshold, free shipping
        BigDecimal result2 = calculator.calculateFreight(new BigDecimal("299.00"));
        assertEquals(BigDecimal.ZERO, result2);
    }

    @Test
    void testCalculate_withTemplateId_matchesTemplate() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setName("Special");
        template.setDefaultFreight(new BigDecimal("20.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));

        when(freightTemplateRepository.findById(1L)).thenReturn(Optional.of(template));

        // 400.00 < 500.00 threshold via template, charges freight
        BigDecimal result = calculator.calculateFreight(new BigDecimal("400.00"), 1L);
        assertEquals(new BigDecimal("20.00"), result);

        // 500.00 reaches the threshold, free shipping
        BigDecimal result2 = calculator.calculateFreight(new BigDecimal("500.00"), 1L);
        assertEquals(BigDecimal.ZERO, result2);
    }

    @Test
    void testCalculate_withTemplateId_nullFallsBackToDefault() {
        when(freightTemplateRepository.findAll()).thenReturn(Collections.emptyList());

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), null);
        assertEquals(new BigDecimal("8.00"), result);
    }

    // ==================== 30-minute templateId cache ====================

    @Test
    void testCalculate_cacheHit_skipsRepositoryLookup() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("12.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L);

        assertEquals(new BigDecimal("12.00"), result);
        verify(freightTemplateRepository, never()).findById(any());
    }

    @Test
    void testCalculate_cacheMiss_populatesCacheFromRepository() {
        FreightTemplate template = new FreightTemplate();
        template.setId(2L);
        template.setDefaultFreight(new BigDecimal("9.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));

        when(freightTemplateCacheManager.get(2L)).thenReturn(null);
        when(freightTemplateRepository.findById(2L)).thenReturn(Optional.of(template));

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 2L);

        assertEquals(new BigDecimal("9.00"), result);
        verify(freightTemplateCacheManager).put(eq(2L), eq(template));
    }

    // ==================== province/weight rule parsing ====================

    @Test
    void testCalculate_provinceRuleMatch_overridesDefaultFreight() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setProvinceRules("[{\"province\":\"Guangdong\",\"freight\":5.00}]");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, "Guangdong", null);

        assertEquals(new BigDecimal("5.00"), result);
    }

    @Test
    void testCalculate_provinceNoMatch_fallsBackToWeightRule() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setProvinceRules("[{\"province\":\"Guangdong\",\"freight\":5.00}]");
        template.setWeightRules("[{\"maxWeightKg\":1.0,\"freight\":8.00},{\"maxWeightKg\":5.0,\"freight\":15.00}]");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, "Beijing",
                new BigDecimal("3.0"));

        assertEquals(new BigDecimal("15.00"), result);
    }

    @Test
    void testCalculate_weightWithinFirstTier_matchesFirstRule() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setWeightRules("[{\"maxWeightKg\":1.0,\"freight\":8.00},{\"maxWeightKg\":5.0,\"freight\":15.00}]");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, null,
                new BigDecimal("0.5"));

        assertEquals(new BigDecimal("8.00"), result);
    }

    @Test
    void testCalculate_weightBeyondAllTiers_fallsBackToDefaultFreight() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setWeightRules("[{\"maxWeightKg\":1.0,\"freight\":8.00},{\"maxWeightKg\":5.0,\"freight\":15.00}]");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, null,
                new BigDecimal("10.0"));

        assertEquals(new BigDecimal("10.00"), result);
    }

    @Test
    void testCalculate_malformedProvinceRulesJson_fallsBackToDefault_doesNotThrow() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setProvinceRules("not-valid-json");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, "Guangdong", null);

        assertEquals(new BigDecimal("10.00"), result);
    }

    @Test
    void testCalculate_malformedWeightRulesJson_fallsBackToDefault_doesNotThrow() {
        FreightTemplate template = new FreightTemplate();
        template.setId(1L);
        template.setDefaultFreight(new BigDecimal("10.00"));
        template.setFreeShippingThreshold(new BigDecimal("500.00"));
        template.setWeightRules("{not-a-list");

        when(freightTemplateCacheManager.get(1L)).thenReturn(template);

        BigDecimal result = calculator.calculateFreight(new BigDecimal("100.00"), 1L, null,
                new BigDecimal("2.0"));

        assertEquals(new BigDecimal("10.00"), result);
    }
}
