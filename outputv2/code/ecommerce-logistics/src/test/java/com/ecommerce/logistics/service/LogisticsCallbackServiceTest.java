package com.ecommerce.logistics.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.logistics.dto.LogisticsCallbackRequest;
import com.ecommerce.logistics.entity.Shipment;
import com.ecommerce.logistics.entity.ShipmentStatus;
import com.ecommerce.logistics.entity.ShipmentTracking;
import com.ecommerce.logistics.repository.ShipmentRepository;
import com.ecommerce.logistics.repository.ShipmentTrackingRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link LogisticsCallbackService}.
 *
 * <p>Verifies real callback processing: mock signature verification, idempotency on
 * trackingNo+eventTime+status, shipment lookup by trackingNo, and status dispatch.
 */
@ExtendWith(MockitoExtension.class)
class LogisticsCallbackServiceTest {

    @Mock
    private ShipmentRepository shipmentRepository;
    @Mock
    private ShipmentTrackingRepository trackingRepository;
    @Mock
    private ShipmentService shipmentService;

    @InjectMocks
    private LogisticsCallbackService callbackService;

    private LogisticsCallbackRequest validRequest(String trackingNo, String status, LocalDateTime eventTime) {
        LogisticsCallbackRequest request = new LogisticsCallbackRequest();
        request.setTrackingNo(trackingNo);
        request.setStatus(status);
        request.setLocation("Shanghai Distribution Center");
        request.setDescription("Package " + status);
        request.setEventTime(eventTime);
        request.setSignature("valid-signature");
        return request;
    }

    @Test
    void testProcessCallback_validSignature_updatesShipmentStatusAndRecordsTracking() {
        LocalDateTime eventTime = LocalDateTime.of(2024, 6, 1, 12, 0);
        LogisticsCallbackRequest request = validRequest("TN12345", "DELIVERED", eventTime);

        Shipment shipment = new Shipment();
        shipment.setId(1L);
        shipment.setTrackingNo("TN12345");

        when(trackingRepository.existsByTrackingNoAndEventTimeAndStatus("TN12345", eventTime, "DELIVERED"))
                .thenReturn(false);
        when(shipmentRepository.findByTrackingNo("TN12345")).thenReturn(Optional.of(shipment));

        callbackService.processCallback(request);

        verify(shipmentService).updateStatus(1L, ShipmentStatus.DELIVERED,
                "Shanghai Distribution Center", "Package DELIVERED");

        ArgumentCaptor<ShipmentTracking> captor = ArgumentCaptor.forClass(ShipmentTracking.class);
        verify(trackingRepository).save(captor.capture());
        ShipmentTracking saved = captor.getValue();
        assertEquals(1L, saved.getShipmentId());
        assertEquals("TN12345", saved.getTrackingNo());
        assertEquals("DELIVERED", saved.getStatus());
        assertEquals(eventTime, saved.getEventTime());
    }

    @Test
    void testProcessCallback_invalidSignature_throwsAuthorizationException_doesNotTouchShipment() {
        LogisticsCallbackRequest request = validRequest("TN12345", "DELIVERED", LocalDateTime.now());
        request.setSignature("bogus-signature");

        assertThrows(AuthorizationException.class, () -> callbackService.processCallback(request));

        verify(shipmentRepository, never()).findByTrackingNo(any());
        verify(shipmentService, never()).updateStatus(any(), any(), any(), any());
        verify(trackingRepository, never()).save(any());
    }

    @Test
    void testProcessCallback_missingSignature_throwsAuthorizationException() {
        LogisticsCallbackRequest request = new LogisticsCallbackRequest();
        request.setTrackingNo("TN99999");
        request.setStatus("IN_TRANSIT");
        // signature intentionally left null

        assertThrows(AuthorizationException.class, () -> callbackService.processCallback(request));
    }

    @Test
    void testProcessCallback_duplicateCallback_isIdempotentNoOp() {
        LocalDateTime eventTime = LocalDateTime.of(2024, 6, 1, 12, 0);
        LogisticsCallbackRequest request = validRequest("TN12345", "DELIVERED", eventTime);

        when(trackingRepository.existsByTrackingNoAndEventTimeAndStatus("TN12345", eventTime, "DELIVERED"))
                .thenReturn(true);

        callbackService.processCallback(request);

        verify(shipmentRepository, never()).findByTrackingNo(any());
        verify(shipmentService, never()).updateStatus(any(), any(), any(), any());
        verify(trackingRepository, never()).save(any());
    }

    @Test
    void testProcessCallback_unknownTrackingNo_throwsResourceNotFound() {
        LogisticsCallbackRequest request = validRequest("UNKNOWN", "DELIVERED", LocalDateTime.now());

        when(trackingRepository.existsByTrackingNoAndEventTimeAndStatus(any(), any(), any()))
                .thenReturn(false);
        when(shipmentRepository.findByTrackingNo("UNKNOWN")).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> callbackService.processCallback(request));
        verify(shipmentService, never()).updateStatus(any(), any(), any(), any());
    }

    @Test
    void testProcessCallback_collectedStatus_mapsToCollected() {
        LogisticsCallbackRequest request = validRequest("TN1", "COLLECTED", LocalDateTime.now());
        Shipment shipment = new Shipment();
        shipment.setId(2L);

        when(trackingRepository.existsByTrackingNoAndEventTimeAndStatus(any(), any(), any())).thenReturn(false);
        when(shipmentRepository.findByTrackingNo("TN1")).thenReturn(Optional.of(shipment));

        callbackService.processCallback(request);

        verify(shipmentService).updateStatus(eq(2L), eq(ShipmentStatus.COLLECTED), any(), any());
    }

    @Test
    void testProcessCallback_exceptionStatus_mapsToException() {
        LogisticsCallbackRequest request = validRequest("TN2", "EXCEPTION", LocalDateTime.now());
        Shipment shipment = new Shipment();
        shipment.setId(3L);

        when(trackingRepository.existsByTrackingNoAndEventTimeAndStatus(any(), any(), any())).thenReturn(false);
        when(shipmentRepository.findByTrackingNo("TN2")).thenReturn(Optional.of(shipment));

        callbackService.processCallback(request);

        verify(shipmentService).updateStatus(eq(3L), eq(ShipmentStatus.EXCEPTION), any(), any());
    }
}
