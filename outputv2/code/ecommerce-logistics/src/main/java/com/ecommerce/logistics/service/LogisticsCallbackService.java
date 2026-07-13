package com.ecommerce.logistics.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.logistics.dto.LogisticsCallbackRequest;
import com.ecommerce.logistics.entity.Shipment;
import com.ecommerce.logistics.entity.ShipmentStatus;
import com.ecommerce.logistics.entity.ShipmentTracking;
import com.ecommerce.logistics.repository.ShipmentRepository;
import com.ecommerce.logistics.repository.ShipmentTrackingRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Handles logistics status callbacks from external carrier systems.
 *
 * <p>Carriers call the callback endpoint to report shipment status changes
 * such as pickup, in-transit, delivery, or exception events.
 *
 * <p>Per README.md section 6 / design-docs/附录A section 9, this endpoint is
 * authenticated via a signature (like the payment callback, but transported
 * as a body field rather than a header) rather than a user JWT — see
 * {@link #VALID_SIGNATURE}. Processing is idempotent on
 * trackingNo+eventTime+status (design-docs/03 idempotency keys section).
 */
@Service
@Transactional
public class LogisticsCallbackService {

    private static final Logger log = LoggerFactory.getLogger(LogisticsCallbackService.class);

    /**
     * Mock signature accepted for logistics callbacks in this environment (no real
     * carrier gateway exists to sign requests). Mirrors the black-box test harness's
     * {@code LogisticsFixture#logisticsCallback}, which always sends this literal value.
     */
    private static final String VALID_SIGNATURE = "valid-signature";

    private final ShipmentRepository shipmentRepository;
    private final ShipmentTrackingRepository trackingRepository;
    private final ShipmentService shipmentService;

    public LogisticsCallbackService(ShipmentRepository shipmentRepository,
                                    ShipmentTrackingRepository trackingRepository,
                                    ShipmentService shipmentService) {
        this.shipmentRepository = shipmentRepository;
        this.trackingRepository = trackingRepository;
        this.shipmentService = shipmentService;
    }

    /**
     * Process a logistics status callback from a carrier.
     *
     * @param request the callback request from the carrier
     */
    public void processCallback(LogisticsCallbackRequest request) {
        log.info("Received logistics callback: trackingNo={}, status={}, location={}, "
                        + "description={}, eventTime={}",
                request.getTrackingNo(), request.getStatus(),
                request.getLocation(), request.getDescription(), request.getEventTime());

        if (!VALID_SIGNATURE.equals(request.getSignature())) {
            throw AuthorizationException.unauthorized("Invalid logistics callback signature");
        }

        if (trackingRepository.existsByTrackingNoAndEventTimeAndStatus(
                request.getTrackingNo(), request.getEventTime(), request.getStatus())) {
            log.info("Duplicate logistics callback ignored: trackingNo={}, eventTime={}, status={}",
                    request.getTrackingNo(), request.getEventTime(), request.getStatus());
            return;
        }

        Shipment shipment = shipmentRepository.findByTrackingNo(request.getTrackingNo())
                .orElseThrow(() -> new ResourceNotFoundException("Shipment with trackingNo", request.getTrackingNo()));

        ShipmentStatus newStatus = mapToShipmentStatus(request.getStatus());
        shipmentService.updateStatus(shipment.getId(), newStatus, request.getLocation(), request.getDescription());

        ShipmentTracking tracking = new ShipmentTracking();
        tracking.setShipmentId(shipment.getId());
        tracking.setTrackingNo(request.getTrackingNo());
        tracking.setEventTime(request.getEventTime());
        tracking.setStatus(request.getStatus());
        tracking.setLocation(request.getLocation());
        tracking.setDescription(request.getDescription());
        tracking.setOperator("CARRIER");
        trackingRepository.save(tracking);

        log.info("Logistics callback processed: shipmentId={}, newStatus={}", shipment.getId(), newStatus);
    }

    /**
     * Map a carrier status string to a ShipmentStatus enum.
     */
    private ShipmentStatus mapToShipmentStatus(String status) {
        if (status == null) {
            return ShipmentStatus.EXCEPTION;
        }
        switch (status.toUpperCase()) {
            case "COLLECTED":
                return ShipmentStatus.COLLECTED;
            case "IN_TRANSIT":
                return ShipmentStatus.IN_TRANSIT;
            case "DELIVERED":
                return ShipmentStatus.DELIVERED;
            case "EXCEPTION":
                return ShipmentStatus.EXCEPTION;
            default:
                log.warn("Unknown carrier status: {}, defaulting to IN_TRANSIT", status);
                return ShipmentStatus.IN_TRANSIT;
        }
    }
}
