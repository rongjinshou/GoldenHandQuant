package com.ecommerce.cart.cache;

import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.common.test.SystemClockService;
import com.github.benmanes.caffeine.cache.Cache;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * Cart storage implementation using Caffeine Cache with 7-day TTL.
 * Key format: userId.
 *
 * <p>The TTL is enforced at two layers: Caffeine's wall-clock
 * {@code expireAfterWrite(7d)} (see CartCacheConfig) remains as the real-time
 * backstop, while {@link #getCart} additionally applies the TTL against
 * {@link SystemClockService} using the runtime-tunable {@code cart.ttl-days}
 * (design-docs/附录B §2, default 7) — so an admin-shifted system clock expires
 * carts deterministically instead of depending on real elapsed time.
 */
@Component
public class CartCacheManager {

    private static final Logger log = LoggerFactory.getLogger(CartCacheManager.class);

    private final Cache<Long, CartData> cartCache;

    public CartCacheManager(Cache<Long, CartData> cartCache) {
        this.cartCache = cartCache;
    }

    /**
     * Retrieves the cart for the given user from the cache.
     *
     * @param userId the user ID
     * @return the cart data, or null if not present or expired
     */
    public CartData getCart(Long userId) {
        CartData cart = cartCache.getIfPresent(userId);
        if (cart == null) {
            log.debug("Cart cache miss for userId={}", userId);
            return null;
        }
        // Application-layer TTL against the test-support clock: entries whose
        // last write is more than cart.ttl-days ago (per SystemClockService)
        // are treated as a miss and dropped, mirroring the 7-day contract even
        // when time is shifted via the admin clock endpoint.
        int ttlDays = RuntimeConfigRegistry.getInt("cart.ttl-days", 7);
        LocalDateTime updatedAt = cart.getUpdatedAt();
        if (updatedAt != null && updatedAt.plusDays(ttlDays).isBefore(SystemClockService.now())) {
            cartCache.invalidate(userId);
            log.debug("Cart cache entry expired by app-layer TTL for userId={} (ttlDays={})",
                    userId, ttlDays);
            return null;
        }
        log.debug("Cart cache hit for userId={}", userId);
        return cart;
    }

    /**
     * Stores or updates the cart for the given user in the cache.
     *
     * @param cart the cart data to store
     */
    public void saveCart(CartData cart) {
        cart.setUpdatedAt(SystemClockService.now());
        cartCache.put(cart.getUserId(), cart);
        log.debug("Cart cached for userId={}", cart.getUserId());
    }

    /**
     * Removes the cart for the given user from the cache.
     *
     * @param userId the user ID
     */
    public void removeCart(Long userId) {
        cartCache.invalidate(userId);
        log.debug("Cart cache invalidated for userId={}", userId);
    }
}
