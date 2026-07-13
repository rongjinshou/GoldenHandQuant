package com.ecommerce.logistics.cache;

import com.ecommerce.logistics.entity.FreightTemplate;
import com.github.benmanes.caffeine.cache.Cache;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Freight template cache using Caffeine Cache with a 30-minute TTL
 * (design-docs/11 section 4). Key format: templateId.
 */
@Component
public class FreightTemplateCacheManager {

    private static final Logger log = LoggerFactory.getLogger(FreightTemplateCacheManager.class);

    private final Cache<Long, FreightTemplate> freightTemplateCache;

    public FreightTemplateCacheManager(Cache<Long, FreightTemplate> freightTemplateCache) {
        this.freightTemplateCache = freightTemplateCache;
    }

    /**
     * Retrieves the cached freight template for the given template id.
     *
     * @param templateId the freight template id
     * @return the cached template, or null if not present or expired
     */
    public FreightTemplate get(Long templateId) {
        FreightTemplate template = freightTemplateCache.getIfPresent(templateId);
        if (template != null) {
            log.debug("Freight template cache hit for templateId={}", templateId);
        } else {
            log.debug("Freight template cache miss for templateId={}", templateId);
        }
        return template;
    }

    /**
     * Stores the freight template for the given template id in the cache.
     *
     * @param templateId the freight template id
     * @param template   the freight template to cache
     */
    public void put(Long templateId, FreightTemplate template) {
        freightTemplateCache.put(templateId, template);
        log.debug("Freight template cached for templateId={}", templateId);
    }

    /**
     * Evicts the cached freight template for the given template id (e.g. after an update/delete).
     *
     * @param templateId the freight template id
     */
    public void evict(Long templateId) {
        freightTemplateCache.invalidate(templateId);
        log.debug("Freight template cache invalidated for templateId={}", templateId);
    }
}
