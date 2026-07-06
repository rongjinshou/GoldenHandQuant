package com.ecommerce.logistics.service;

import com.ecommerce.logistics.cache.FreightTemplateCacheManager;
import com.ecommerce.logistics.entity.FreightTemplate;
import com.ecommerce.logistics.repository.FreightTemplateRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Calculates shipping freight based on item total and freight templates.
 *
 * <p>Default rules:
 * <ul>
 *   <li>Default freight: 8.00</li>
 *   <li>Free shipping when item total reaches the free-shipping threshold</li>
 * </ul>
 *
 * <p>When a specific freight template applies (design-docs/11 section 4), its
 * province- and weight-based rules are consulted (in that order) before
 * falling back to the template's own default freight. Templates are resolved
 * through a 30-minute cache keyed by templateId ({@link FreightTemplateCacheManager}).
 */
@Service
public class FreightCalculator {

    private static final Logger log = LoggerFactory.getLogger(FreightCalculator.class);

    private static final BigDecimal DEFAULT_FREIGHT = new BigDecimal("8.00");
    private static final BigDecimal DEFAULT_FREE_SHIPPING_THRESHOLD = new BigDecimal("199.00");

    private final FreightTemplateRepository freightTemplateRepository;
    private final FreightTemplateCacheManager freightTemplateCacheManager;
    private final ObjectMapper objectMapper;

    public FreightCalculator(FreightTemplateRepository freightTemplateRepository,
                             FreightTemplateCacheManager freightTemplateCacheManager,
                             ObjectMapper objectMapper) {
        this.freightTemplateRepository = freightTemplateRepository;
        this.freightTemplateCacheManager = freightTemplateCacheManager;
        this.objectMapper = objectMapper;
    }

    /**
     * Calculate the freight for an order based on item total.
     *
     * @param itemTotal the total price of items in the order
     * @return the freight amount (0.00 if free shipping applies)
     */
    public BigDecimal calculateFreight(BigDecimal itemTotal) {
        return calculateFreight(itemTotal, null, null, null);
    }

    /**
     * Calculate freight for a specific item total and template ID.
     */
    public BigDecimal calculateFreight(BigDecimal itemTotal, Long templateId) {
        if (templateId == null) {
            return calculateFreight(itemTotal);
        }
        return calculateFreight(itemTotal, templateId, null, null);
    }

    /**
     * Calculate freight for an order, optionally applying a specific template's
     * province- or weight-based rules (design-docs/11 section 4).
     *
     * @param itemTotal  the total price of items in the order
     * @param templateId optional freight template to apply; resolved via a 30-minute cache
     * @param province   optional delivery province, matched against the template's province rules
     * @param weight     optional package weight in kg, matched against the template's weight rules
     * @return the freight amount (0.00 if free shipping applies)
     */
    public BigDecimal calculateFreight(BigDecimal itemTotal, Long templateId, String province, BigDecimal weight) {
        if (itemTotal == null || itemTotal.compareTo(BigDecimal.ZERO) <= 0) {
            return DEFAULT_FREIGHT;
        }

        FreightTemplate template = templateId != null ? loadTemplate(templateId) : findActiveTemplate();

        if (template == null) {
            if (itemTotal.compareTo(DEFAULT_FREE_SHIPPING_THRESHOLD) >= 0) {
                log.info("Free shipping (default): itemTotal={} reaches threshold={}",
                        itemTotal, DEFAULT_FREE_SHIPPING_THRESHOLD);
                return BigDecimal.ZERO;
            }
            log.info("Freight charged (default): itemTotal={}, freight={}", itemTotal, DEFAULT_FREIGHT);
            return DEFAULT_FREIGHT;
        }

        BigDecimal threshold = template.getFreeShippingThreshold() != null
                ? template.getFreeShippingThreshold() : DEFAULT_FREE_SHIPPING_THRESHOLD;

        if (itemTotal.compareTo(threshold) >= 0) {
            log.info("Free shipping: itemTotal={} reaches threshold={}", itemTotal, threshold);
            return BigDecimal.ZERO;
        }

        BigDecimal freight = resolveFreight(template, province, weight);
        log.info("Freight charged: itemTotal={}, threshold={}, freight={}", itemTotal, threshold, freight);
        return freight;
    }

    /**
     * Resolves a freight template by id through the 30-minute cache, loading from
     * the repository (and re-populating the cache) on a miss.
     */
    private FreightTemplate loadTemplate(Long templateId) {
        FreightTemplate cached = freightTemplateCacheManager.get(templateId);
        if (cached != null) {
            return cached;
        }
        FreightTemplate template = freightTemplateRepository.findById(templateId).orElse(null);
        if (template != null) {
            freightTemplateCacheManager.put(templateId, template);
        }
        return template;
    }

    /**
     * Applies a template's province rule (if the province matches) or weight rule
     * (if the weight falls within a configured tier), falling back to the
     * template's own default freight when neither axis matches or is provided.
     */
    private BigDecimal resolveFreight(FreightTemplate template, String province, BigDecimal weight) {
        BigDecimal defaultFreight = template.getDefaultFreight() != null
                ? template.getDefaultFreight() : DEFAULT_FREIGHT;

        if (province != null && !province.isBlank()) {
            BigDecimal provinceRate = parseProvinceRules(template.getProvinceRules()).get(province);
            if (provinceRate != null) {
                return provinceRate;
            }
        }

        if (weight != null) {
            for (WeightRule rule : parseWeightRules(template.getWeightRules())) {
                if (rule.getMaxWeightKg() != null && weight.compareTo(rule.getMaxWeightKg()) <= 0) {
                    return rule.getFreight();
                }
            }
        }

        return defaultFreight;
    }

    /**
     * Parses {@code provinceRules} JSON (format: {@code [{"province":"Guangdong","freight":5.00}]}).
     * Returns an empty map (falling back to the template default) on any parse failure or blank input.
     */
    private Map<String, BigDecimal> parseProvinceRules(String json) {
        if (json == null || json.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            List<ProvinceRule> rules = objectMapper.readValue(json, new TypeReference<List<ProvinceRule>>() { });
            Map<String, BigDecimal> byProvince = new HashMap<>();
            for (ProvinceRule rule : rules) {
                if (rule.getProvince() != null && rule.getFreight() != null) {
                    byProvince.put(rule.getProvince(), rule.getFreight());
                }
            }
            return byProvince;
        } catch (Exception e) {
            log.warn("Failed to parse freight template provinceRules, falling back to default freight: {}",
                    e.getMessage());
            return Collections.emptyMap();
        }
    }

    /**
     * Parses {@code weightRules} JSON (format:
     * {@code [{"maxWeightKg":1.0,"freight":8.00},{"maxWeightKg":5.0,"freight":15.00}]}), sorted
     * ascending by {@code maxWeightKg} so the first tier the weight fits under wins.
     * Returns an empty list (falling back to the template default) on any parse failure or blank input.
     */
    private List<WeightRule> parseWeightRules(String json) {
        if (json == null || json.isBlank()) {
            return Collections.emptyList();
        }
        try {
            List<WeightRule> rules = objectMapper.readValue(json, new TypeReference<List<WeightRule>>() { });
            rules.sort(Comparator.comparing(WeightRule::getMaxWeightKg,
                    Comparator.nullsLast(Comparator.naturalOrder())));
            return rules;
        } catch (Exception e) {
            log.warn("Failed to parse freight template weightRules, falling back to default freight: {}",
                    e.getMessage());
            return Collections.emptyList();
        }
    }

    private FreightTemplate findActiveTemplate() {
        return freightTemplateRepository.findAll()
                .stream()
                .findFirst()
                .orElse(null);
    }

    /** JSON shape: {"province":"Guangdong","freight":5.00} */
    private static class ProvinceRule {
        private String province;
        private BigDecimal freight;

        public String getProvince() {
            return province;
        }

        public void setProvince(String province) {
            this.province = province;
        }

        public BigDecimal getFreight() {
            return freight;
        }

        public void setFreight(BigDecimal freight) {
            this.freight = freight;
        }
    }

    /** JSON shape: {"maxWeightKg":1.0,"freight":8.00} */
    private static class WeightRule {
        private BigDecimal maxWeightKg;
        private BigDecimal freight;

        public BigDecimal getMaxWeightKg() {
            return maxWeightKg;
        }

        public void setMaxWeightKg(BigDecimal maxWeightKg) {
            this.maxWeightKg = maxWeightKg;
        }

        public BigDecimal getFreight() {
            return freight;
        }

        public void setFreight(BigDecimal freight) {
            this.freight = freight;
        }
    }
}
