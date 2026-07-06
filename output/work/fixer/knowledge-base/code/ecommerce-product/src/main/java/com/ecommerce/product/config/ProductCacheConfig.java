package com.ecommerce.product.config;

import com.ecommerce.product.dto.ProductDetailResponse;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

/**
 * Configuration for the Caffeine Cache used to store product detail responses.
 *
 * <p>Creates a {@link Cache} bean with a 10-minute TTL, keyed by skuId
 * (design-docs/02 section 7: {@code product:detail:{skuId}}, TTL 10 分钟).
 */
@Configuration
public class ProductCacheConfig {

    private static final Logger log = LoggerFactory.getLogger(ProductCacheConfig.class);

    /**
     * The TTL for product detail cache entries: 10 minutes.
     */
    private static final Duration PRODUCT_DETAIL_TTL = Duration.ofMinutes(10);

    /**
     * Maximum number of product detail entries in the cache.
     */
    private static final long MAX_PRODUCT_DETAIL_ENTRIES = 10_000;

    /**
     * Creates a Caffeine Cache bean for storing {@link ProductDetailResponse} keyed by skuId.
     * TTL is 10 minutes, after which entries are automatically evicted.
     */
    @Bean
    public Cache<Long, ProductDetailResponse> productDetailCache() {
        log.info("Initializing product detail cache with TTL={}, maxSize={}",
                PRODUCT_DETAIL_TTL, MAX_PRODUCT_DETAIL_ENTRIES);
        return Caffeine.newBuilder()
                .expireAfterWrite(PRODUCT_DETAIL_TTL)
                .maximumSize(MAX_PRODUCT_DETAIL_ENTRIES)
                .recordStats()
                .build();
    }
}
