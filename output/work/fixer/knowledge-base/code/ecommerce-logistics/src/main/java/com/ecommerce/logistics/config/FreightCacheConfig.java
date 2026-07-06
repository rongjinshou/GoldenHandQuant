package com.ecommerce.logistics.config;

import com.ecommerce.logistics.entity.FreightTemplate;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

/**
 * Configuration for the Caffeine Cache used to store resolved freight templates.
 *
 * <p>Creates a {@link Cache} bean with a 30-minute TTL, keyed by templateId
 * (design-docs/11 section 4: freight templates are resolved once and reused
 * for up to 30 minutes rather than hitting the repository on every freight
 * calculation).
 */
@Configuration
public class FreightCacheConfig {

    private static final Logger log = LoggerFactory.getLogger(FreightCacheConfig.class);

    /**
     * The TTL for freight template cache entries: 30 minutes.
     */
    private static final Duration FREIGHT_TEMPLATE_TTL = Duration.ofMinutes(30);

    /**
     * Maximum number of freight template entries in the cache.
     */
    private static final long MAX_FREIGHT_TEMPLATE_ENTRIES = 10_000;

    /**
     * Creates a Caffeine Cache bean for storing {@link FreightTemplate} keyed by templateId.
     * TTL is 30 minutes, after which entries are automatically evicted.
     */
    @Bean
    public Cache<Long, FreightTemplate> freightTemplateCache() {
        log.info("Initializing freight template cache with TTL={}, maxSize={}",
                FREIGHT_TEMPLATE_TTL, MAX_FREIGHT_TEMPLATE_ENTRIES);
        return Caffeine.newBuilder()
                .expireAfterWrite(FREIGHT_TEMPLATE_TTL)
                .maximumSize(MAX_FREIGHT_TEMPLATE_ENTRIES)
                .recordStats()
                .build();
    }
}
