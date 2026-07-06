package com.ecommerce.inventory.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;
import java.util.List;

/**
 * Cache configuration for the inventory module's stock-summary cache
 * (design-docs/02 section 7: "库存摘要 | inventory:summary:{skuId} | 30 秒 | inventory").
 *
 * <p>The {@link CacheManager} bean is registered under an explicit name
 * ({@code inventoryCacheManager}) and every {@code @Cacheable}/{@code @CacheEvict}
 * annotation in this module references it by that name. This keeps the inventory
 * module's caching fully self-contained: it neither depends on, nor competes
 * with, whatever {@link CacheManager} bean(s) other modules (e.g. cart's
 * Caffeine-backed cart cache, or product's own cache config) register in the
 * same application context.
 */
@Configuration
@EnableCaching
public class InventoryCacheConfig {

    /**
     * TTL for the inventory stock-summary cache: 30 seconds per design-docs/02 section 7.
     */
    private static final Duration STOCK_SUMMARY_TTL = Duration.ofSeconds(30);

    private static final long MAX_CACHE_ENTRIES = 10_000;

    @Bean
    public CacheManager inventoryCacheManager() {
        CaffeineCacheManager cacheManager = new CaffeineCacheManager();
        // Fixed cache name set (rather than allow-dynamic-creation) so every cache
        // this manager serves gets the same 30s spec below.
        cacheManager.setCacheNames(List.of(com.ecommerce.inventory.service.InventoryService.INVENTORY_SUMMARY_CACHE));
        cacheManager.setCaffeine(Caffeine.newBuilder()
                .expireAfterWrite(STOCK_SUMMARY_TTL)
                .maximumSize(MAX_CACHE_ENTRIES)
                .recordStats());
        return cacheManager;
    }
}
