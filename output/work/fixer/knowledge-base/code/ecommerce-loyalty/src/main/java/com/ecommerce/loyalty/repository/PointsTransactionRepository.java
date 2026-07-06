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
}
