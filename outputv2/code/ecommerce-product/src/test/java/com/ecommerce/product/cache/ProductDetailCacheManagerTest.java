package com.ecommerce.product.cache;

import com.ecommerce.product.dto.ProductDetailResponse;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("ProductDetailCacheManager")
class ProductDetailCacheManagerTest {

    private ProductDetailCacheManager cacheManager;
    private Cache<Long, ProductDetailResponse> cache;

    private static final Long SKU_ID = 1L;

    @BeforeEach
    void setUp() {
        cache = Caffeine.newBuilder()
                .maximumSize(100)
                .build();
        cacheManager = new ProductDetailCacheManager(cache);
    }

    @Test
    @DisplayName("get returns null when entry is not in cache")
    void testGet_notInCache_returnsNull() {
        assertThat(cacheManager.get(SKU_ID)).isNull();
    }

    @Test
    @DisplayName("put then get returns the same data")
    void testPutAndGet_returnsSameData() {
        ProductDetailResponse detail = new ProductDetailResponse();
        detail.setSkuId(SKU_ID);
        detail.setName("Test SKU");

        cacheManager.put(SKU_ID, detail);

        ProductDetailResponse retrieved = cacheManager.get(SKU_ID);
        assertThat(retrieved).isNotNull();
        assertThat(retrieved.getSkuId()).isEqualTo(SKU_ID);
        assertThat(retrieved.getName()).isEqualTo("Test SKU");
    }

    @Test
    @DisplayName("cache TTL evicts entries after expiration period")
    void testCacheExpiry_ttl10Minutes() throws InterruptedException {
        // Use a short TTL to verify the expiry mechanism works
        Cache<Long, ProductDetailResponse> shortTtlCache = Caffeine.newBuilder()
                .expireAfterWrite(Duration.ofMillis(200))
                .maximumSize(100)
                .build();
        ProductDetailCacheManager shortTtlManager = new ProductDetailCacheManager(shortTtlCache);

        ProductDetailResponse detail = new ProductDetailResponse();
        detail.setSkuId(SKU_ID);
        shortTtlManager.put(SKU_ID, detail);

        assertThat(shortTtlManager.get(SKU_ID)).isNotNull();

        Thread.sleep(300);

        assertThat(shortTtlManager.get(SKU_ID)).isNull();
    }

    @Test
    @DisplayName("evict clears the entry so get returns null afterwards")
    void testEvict_clearsEntry() {
        ProductDetailResponse detail = new ProductDetailResponse();
        detail.setSkuId(SKU_ID);
        cacheManager.put(SKU_ID, detail);

        assertThat(cacheManager.get(SKU_ID)).isNotNull();

        cacheManager.evict(SKU_ID);

        assertThat(cacheManager.get(SKU_ID)).isNull();
    }

    @Test
    @DisplayName("put overwrites any previously-cached value for the same skuId")
    void testPut_overwritesPreviousValue() {
        ProductDetailResponse first = new ProductDetailResponse();
        first.setSkuId(SKU_ID);
        first.setStatus("ON_SHELF");
        cacheManager.put(SKU_ID, first);

        ProductDetailResponse second = new ProductDetailResponse();
        second.setSkuId(SKU_ID);
        second.setStatus("OFF_SHELF");
        cacheManager.put(SKU_ID, second);

        assertThat(cacheManager.get(SKU_ID).getStatus()).isEqualTo("OFF_SHELF");
    }
}
