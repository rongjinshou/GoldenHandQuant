package com.ecommerce.user.query;

/**
 * Cross-module query service for user and address information.
 * Other modules (order, payment, review, etc.) depend on this interface,
 * never on user repositories directly.
 */
public interface UserQueryService {

    /**
     * Retrieves basic user information by userId.
     *
     * @param userId the user ID
     * @return the user DTO, never null (throws {@code ResourceNotFoundException} if missing)
     */
    UserDto getUserById(Long userId);

    /**
     * Returns true if the user status is ACTIVE.
     *
     * @param userId the user ID
     * @return true if active, false otherwise (including when the user does not exist)
     */
    boolean isActive(Long userId);

    /**
     * Returns true if the user status is FROZEN.
     *
     * @param userId the user ID
     * @return true if frozen, false otherwise (including when the user does not exist)
     */
    boolean isFrozen(Long userId);

    /**
     * Retrieves the default shipping address for a user.
     *
     * @param userId the user ID
     * @return the default address DTO, or null if none exists
     */
    AddressDto getDefaultAddress(Long userId);

    /**
     * Retrieves a specific address by ID, verifying it belongs to the given user
     * (附录A: order creation's {@code addressId} selects a specific address, not
     * necessarily the default one).
     *
     * @param userId    the user ID
     * @param addressId the address ID
     * @return the address DTO (throws {@code ResourceNotFoundException} if it
     *         doesn't exist or doesn't belong to this user)
     */
    AddressDto getAddressById(Long userId, Long addressId);
}
