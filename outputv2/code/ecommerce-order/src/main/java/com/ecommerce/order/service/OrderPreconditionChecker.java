package com.ecommerce.order.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.user.query.UserDto;
import com.ecommerce.user.query.UserQueryService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Validates preconditions before creating an order.
 */
@Component
public class OrderPreconditionChecker {

    private static final Logger log = LoggerFactory.getLogger(OrderPreconditionChecker.class);

    // Fallback only; 附录B default is 30 (order.max-items), overridable at runtime.
    private static final int DEFAULT_MAX_ITEMS = 30;

    private final UserQueryService userQueryService;

    public OrderPreconditionChecker(UserQueryService userQueryService) {
        this.userQueryService = userQueryService;
    }

    /**
     * Check that all preconditions for order creation are met.
     *
     * @param userId    the user ID
     * @param itemCount the number of items in the order
     * @throws BusinessException if user does not exist
     */
    public void check(Long userId, int itemCount) {
        UserDto user = userQueryService.getUserById(userId);
        if (user == null) {
            throw new BusinessException("USER_NOT_FOUND", "User not found: " + userId);
        }

        if (userQueryService.isFrozen(userId)) {
            throw new AuthorizationException("USER_FROZEN", "User is frozen: " + userId);
        }

        if (itemCount <= 0) {
            throw new BusinessException("ORDER_EMPTY", "Order must have at least one item");
        }

        int maxItems = RuntimeConfigRegistry.getInt("order.max-items", DEFAULT_MAX_ITEMS);
        if (itemCount > maxItems) {
            throw new BusinessException("ORDER_ITEMS_LIMIT_EXCEEDED",
                    "Order item count " + itemCount + " exceeds the limit of " + maxItems);
        }

        log.debug("Order preconditions passed for userId={}, itemCount={}", userId, itemCount);
    }
}
