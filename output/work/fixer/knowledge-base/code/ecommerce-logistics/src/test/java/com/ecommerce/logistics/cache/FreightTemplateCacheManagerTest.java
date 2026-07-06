package com.ecommerce.logistics.cache;

import com.ecommerce.logistics.entity.FreightTemplate;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("FreightTemplateCacheManager")
class FreightTemplateCacheManagerTest {

    private FreightTemplateCacheManager cacheManager;
    private Cache<Long, FreightTemplate> cache;

    private static final Long TEMPLATE_ID = 1L;

    @BeforeEach
    void setUp() {
        cache = Caffeine.newBuilder()
                .maximumSize(100)
                .build();
        cacheManager = new FreightTemplateCacheManager(cache);
    }

    @Test
    @DisplayName("get returns null when entry is not in cache")
    void testGet_notInCache_returnsNull() {
        assertThat(cacheManager.get(TEMPLATE_ID)).isNull();
    }

    @Test
    @DisplayName("put then get returns the same data")
    void testPutAndGet_returnsSameData() {
        FreightTemplate template = new FreightTemplate();
        template.setId(TEMPLATE_ID);
        template.setName("Standard Shipping");
        template.setDefaultFreight(new BigDecimal("8.00"));

        cacheManager.put(TEMPLATE_ID, template);

        FreightTemplate retrieved = cacheManager.get(TEMPLATE_ID);
        assertThat(retrieved).isNotNull();
        assertThat(retrieved.getId()).isEqualTo(TEMPLATE_ID);
        assertThat(retrieved.getDefaultFreight()).isEqualByComparingTo("8.00");
    }

    @Test
    @DisplayName("cache TTL evicts entries after expiration period")
    void testCacheExpiry_ttl30Minutes() throws InterruptedException {
        // Use a short TTL to verify the expiry mechanism works
        Cache<Long, FreightTemplate> shortTtlCache = Caffeine.newBuilder()
                .expireAfterWrite(Duration.ofMillis(200))
                .maximumSize(100)
                .build();
        FreightTemplateCacheManager shortTtlManager = new FreightTemplateCacheManager(shortTtlCache);

        FreightTemplate template = new FreightTemplate();
        template.setId(TEMPLATE_ID);
        shortTtlManager.put(TEMPLATE_ID, template);

        assertThat(shortTtlManager.get(TEMPLATE_ID)).isNotNull();

        Thread.sleep(300);

        assertThat(shortTtlManager.get(TEMPLATE_ID)).isNull();
    }

    @Test
    @DisplayName("evict clears the entry so get returns null afterwards")
    void testEvict_clearsEntry() {
        FreightTemplate template = new FreightTemplate();
        template.setId(TEMPLATE_ID);
        cacheManager.put(TEMPLATE_ID, template);

        assertThat(cacheManager.get(TEMPLATE_ID)).isNotNull();

        cacheManager.evict(TEMPLATE_ID);

        assertThat(cacheManager.get(TEMPLATE_ID)).isNull();
    }

    @Test
    @DisplayName("put overwrites any previously-cached value for the same templateId")
    void testPut_overwritesPreviousValue() {
        FreightTemplate first = new FreightTemplate();
        first.setId(TEMPLATE_ID);
        first.setDefaultFreight(new BigDecimal("8.00"));
        cacheManager.put(TEMPLATE_ID, first);

        FreightTemplate second = new FreightTemplate();
        second.setId(TEMPLATE_ID);
        second.setDefaultFreight(new BigDecimal("12.00"));
        cacheManager.put(TEMPLATE_ID, second);

        assertThat(cacheManager.get(TEMPLATE_ID).getDefaultFreight()).isEqualByComparingTo("12.00");
    }
}
