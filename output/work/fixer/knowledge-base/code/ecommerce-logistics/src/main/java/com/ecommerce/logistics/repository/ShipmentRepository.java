package com.ecommerce.logistics.repository;

import com.ecommerce.logistics.entity.Shipment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Repository for {@link Shipment} entities.
 */
@Repository
public interface ShipmentRepository extends JpaRepository<Shipment, Long> {

    /**
     * Find a shipment by its associated order ID.
     */
    Optional<Shipment> findByOrderId(Long orderId);

    /**
     * Find a shipment by its unique shipment number.
     */
    Optional<Shipment> findByShipmentNo(String shipmentNo);

    /**
     * Find a shipment by its carrier tracking number (assigned at label-print time).
     * Used to resolve the shipment targeted by an inbound logistics carrier callback.
     */
    Optional<Shipment> findByTrackingNo(String trackingNo);
}
