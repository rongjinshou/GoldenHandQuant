package com.ecommerce.product.cache;

import com.ecommerce.product.dto.ProductDetailResponse;
import com.github.benmanes.caffeine.cache.Cache;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Product detail cache using Caffeine Cache with a 10-minute TTL
 * (design-docs/02 section 7: {@code product:detail:{skuId}}).
 * Key format: skuId.
 */
@Component
public class ProductDetailCacheManager {

    private static final Logger log = LoggerFactory.getLogger(ProductDetailCacheManager.class);

    private final Cache<Long, ProductDetailResponse> productDetailCache;

    public ProductDetailCacheManager(Cache<Long, ProductDetailResponse> productDetailCache) {
        this.productDetailCache = productDetailCache;
    }

    /**
     * Retrieves the cached product detail for the given SKU.
     *
     * @param skuId the SKU id
     * @return the cached product detail, or null if not present or expired
     */
    public ProductDetailResponse get(Long skuId) {
        ProductDetailResponse detail = productDetailCache.getIfPresent(skuId);
        if (detail != null) {
            log.debug("Product detail cache hit for skuId={}", skuId);
        } else {
            log.debug("Product detail cache miss for skuId={}", skuId);
        }
        return detail;
    }

    /**
     * Stores the product detail for the given SKU in the cache.
     *
     * @param skuId  the SKU id
     * @param detail the product detail to cache
     */
    public void put(Long skuId, ProductDetailResponse detail) {
        productDetailCache.put(skuId, detail);
        log.debug("Product detail cached for skuId={}", skuId);
    }

    /**
     * Evicts the cached product detail for the given SKU (e.g. after an on/off-shelf change).
     *
     * @param skuId the SKU id
     */
    public void evict(Long skuId) {
        productDetailCache.invalidate(skuId);
        log.debug("Product detail cache invalidated for skuId={}", skuId);
    }
}
