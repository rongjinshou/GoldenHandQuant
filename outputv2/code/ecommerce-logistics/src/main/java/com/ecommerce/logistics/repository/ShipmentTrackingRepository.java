package com.ecommerce.logistics.repository;

import com.ecommerce.logistics.entity.ShipmentTracking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Repository for {@link ShipmentTracking} entities.
 */
@Repository
public interface ShipmentTrackingRepository extends JpaRepository<ShipmentTracking, Long> {

    /**
     * Find all tracking records for a shipment, ordered by event time.
     */
    List<ShipmentTracking> findByShipmentIdOrderByEventTimeAsc(Long shipmentId);

    /**
     * Idempotency check for logistics carrier callbacks: trackingNo + eventTime + status
     * (design-docs/03 idempotency keys section). Returns true if this exact callback event
     * has already been recorded, so it can be safely no-op'd on retry/duplicate delivery.
     */
    boolean existsByTrackingNoAndEventTimeAndStatus(String trackingNo, LocalDateTime eventTime, String status);
}
