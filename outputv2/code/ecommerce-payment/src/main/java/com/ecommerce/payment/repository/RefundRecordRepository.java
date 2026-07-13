package com.ecommerce.payment.repository;

import com.ecommerce.payment.entity.RefundRecord;
import com.ecommerce.payment.entity.RefundStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface RefundRecordRepository extends JpaRepository<RefundRecord, Long> {

    Optional<RefundRecord> findByRefundNo(String refundNo);

    Optional<RefundRecord> findByRefundRequestNo(String refundRequestNo);

    List<RefundRecord> findByPaymentNo(String paymentNo);

    List<RefundRecord> findByOrderId(Long orderId);

    List<RefundRecord> findByUserId(Long userId);

    List<RefundRecord> findByStatus(RefundStatus status);

    List<RefundRecord> findByStatusAndCompletedAtBetween(
            RefundStatus status, LocalDateTime start, LocalDateTime end);
}
