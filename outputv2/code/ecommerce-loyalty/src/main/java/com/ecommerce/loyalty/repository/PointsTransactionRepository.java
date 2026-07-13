package com.ecommerce.loyalty.repository;

import com.ecommerce.loyalty.entity.PointsTransaction;
import com.ecommerce.loyalty.entity.PointsTransactionType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Spring Data JPA repository for {@link PointsTransaction}.
 */
@Repository
public interface PointsTransactionRepository extends JpaRepository<PointsTransaction, Long> {

    /**
     * Find paged points transactions for a user, ordered by creation time descending.
     *
     * @param userId   the user's ID
     * @param pageable pagination information
     * @return a page of points transactions
     */
    Page<PointsTransaction> findByUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);

    /**
     * Find EARN transactions that are past their expiry cutoff and have not
     * yet been processed by {@link com.ecommerce.loyalty.service.PointsExpireService}.
     *
     * @param type   the transaction type to scan (always {@code EARN})
     * @param cutoff transactions with {@code expiresAt <= cutoff} are eligible
     * @return the list of transactions eligible for expiry processing
     */
    List<PointsTransaction> findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
            PointsTransactionType type, LocalDateTime cutoff);

    /**
     * Find the transactions of a given type recorded against a business id.
     * For REDEEM rows, {@code bizId} is the id of the order that consumed the
     * points — used to reverse that deduction when the order is cancelled.
     *
     * @param type  the transaction type
     * @param bizId the business entity id the transaction references
     * @return the matching transactions (empty if none)
     */
    List<PointsTransaction> findByTypeAndBizId(PointsTransactionType type, String bizId);

    /**
     * Whether a transaction of the given type already references this
     * business id. Idempotency guard for order-cancel refunds: a REFUND row
     * with the order's id means that order's deduction was already given back.
     *
     * @param type  the transaction type
     * @param bizId the business entity id the transaction references
     * @return {@code true} if such a transaction exists
     */
    boolean existsByTypeAndBizId(PointsTransactionType type, String bizId);
}
