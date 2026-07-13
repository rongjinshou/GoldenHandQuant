package com.ecommerce.logistics.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.ShipmentDeliveredEvent;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.logistics.dto.ShipmentResponse;
import com.ecommerce.logistics.entity.PickList;
import com.ecommerce.logistics.entity.Shipment;
import com.ecommerce.logistics.entity.ShipmentStatus;
import com.ecommerce.logistics.entity.ShipmentTracking;
import com.ecommerce.logistics.query.OrderLogisticsStatusUpdater;
import com.ecommerce.logistics.repository.LabelRecordRepository;
import com.ecommerce.logistics.repository.PickListRepository;
import com.ecommerce.logistics.repository.ShipmentRepository;
import com.ecommerce.logistics.repository.ShipmentTrackingRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link ShipmentService}.
 *
 * <p>Verifies shipment creation, the CREATED -&gt; PICKING -&gt; LABEL_PRINTED -&gt; OUTBOUND
 * state machine (design-docs/11 sections 2/3), and DELIVERED event publishing.
 */
@ExtendWith(MockitoExtension.class)
class ShipmentServiceTest {

    @Mock
    private ShipmentRepository shipmentRepository;
    @Mock
    private PickListRepository pickListRepository;
    @Mock
    private LabelRecordRepository labelRecordRepository;
    @Mock
    private ShipmentTrackingRepository trackingRepository;
    @Mock
    private FreightCalculator freightCalculator;
    @Mock
    private OrderLogisticsStatusUpdater orderLogisticsStatusUpdater;
    @Mock
    private DomainEventPublisher eventPublisher;

    @InjectMocks
    private ShipmentService shipmentService;

    // ==================== createShipment ====================

    /**
     * Per design-docs/11 section 3, a freshly-created shipment starts at CREATED;
     * the correct progression is CREATED -> PICKING -> LABEL_PRINTED -> OUTBOUND.
     */
    @Test
    void createShipment_startsAtCreated_notOutbound() {
        when(shipmentRepository.save(any(Shipment.class))).thenAnswer(inv -> {
            Shipment s = inv.getArgument(0);
            s.setId(1L);
            return s;
        });

        Shipment result = shipmentService.createShipment(100L, 200L,
                new BigDecimal("8.00"), "{\"province\":\"Beijing\"}");

        assertNotNull(result);
        assertEquals(100L, result.getOrderId());
        assertEquals(200L, result.getUserId());
        assertEquals(new BigDecimal("8.00"), result.getFreightAmount());
        assertEquals("{\"province\":\"Beijing\"}", result.getAddressSnapshot());
        assertNotNull(result.getShipmentNo());
        assertEquals(ShipmentStatus.CREATED, result.getStatus(),
                "createShipment must start the shipment at CREATED, not OUTBOUND");
    }

    @Test
    void testCreateShipment_nullFreight_defaultsToZero() {
        when(shipmentRepository.save(any(Shipment.class))).thenAnswer(inv -> {
            Shipment s = inv.getArgument(0);
            s.setId(1L);
            return s;
        });

        Shipment result = shipmentService.createShipment(100L, 200L,
                null, "");

        assertEquals(BigDecimal.ZERO, result.getFreightAmount());
    }

    // ==================== pick ====================

    @Test
    void testPick_fromCreated_canPick() {
        Shipment shipment = createShipment(2L, ShipmentStatus.CREATED);
        when(shipmentRepository.findById(2L)).thenReturn(Optional.of(shipment));
        when(pickListRepository.save(any(PickList.class))).thenAnswer(inv -> {
            PickList pl = inv.getArgument(0);
            pl.setId(11L);
            return pl;
        });
        when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());

        shipmentService.pick(2L, 888L);

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        assertEquals(ShipmentStatus.PICKING, captor.getValue().getStatus());
    }

    @Test
    void testPick_fromPicking_staysPicking() {
        Shipment shipment = createShipment(3L, ShipmentStatus.PICKING);
        shipment.setPickListId(5L);
        when(shipmentRepository.findById(3L)).thenReturn(Optional.of(shipment));
        when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());

        shipmentService.pick(3L, 777L);

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        // Status stays PICKING, no new pick list is created (already has pickListId)
        assertEquals(ShipmentStatus.PICKING, captor.getValue().getStatus());
    }

    @Test
    void testPick_fromOutbound_throwsConflict() {
        Shipment shipment = createShipment(1L, ShipmentStatus.OUTBOUND);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        assertThrows(ConflictException.class, () -> shipmentService.pick(1L, 999L),
                "pick() must not allow OUTBOUND -> PICKING (no going backwards after outbound)");
    }

    @Test
    void testPick_fromCollected_throwsException() {
        Shipment shipment = createShipment(4L, ShipmentStatus.COLLECTED);
        when(shipmentRepository.findById(4L)).thenReturn(Optional.of(shipment));

        assertThrows(ConflictException.class,
                () -> shipmentService.pick(4L, 666L));
    }

    @Test
    void testPick_fromDelivered_throwsException() {
        Shipment shipment = createShipment(5L, ShipmentStatus.DELIVERED);
        when(shipmentRepository.findById(5L)).thenReturn(Optional.of(shipment));

        assertThrows(ConflictException.class,
                () -> shipmentService.pick(5L, 555L));
    }

    // ==================== printLabel ====================

    @Test
    void testPrintLabel_transitionsToLabelPrinted() {
        Shipment shipment = createShipment(1L, ShipmentStatus.PICKING);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));
        when(labelRecordRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());

        shipmentService.printLabel(1L, "SF");

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        Shipment saved = captor.getValue();
        assertEquals(ShipmentStatus.LABEL_PRINTED, saved.getStatus());
        assertEquals("SF", saved.getCarrier());
        assertNotNull(saved.getLabelNo());
        assertNotNull(saved.getTrackingNo());
    }

    @Test
    void printLabel_beforePicking_throwsConflict() {
        Shipment shipment = createShipment(1L, ShipmentStatus.CREATED);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        assertThrows(ConflictException.class, () -> shipmentService.printLabel(shipment.getId(), "SF"));
    }

    // ==================== outbound ====================

    @Test
    void testOutbound_transitionsToOutbound() {
        Shipment shipment = createShipment(1L, ShipmentStatus.LABEL_PRINTED);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));
        when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());

        shipmentService.outbound(1L);

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        assertEquals(ShipmentStatus.OUTBOUND, captor.getValue().getStatus());
    }

    @Test
    void outbound_beforeLabelPrinted_throwsConflict() {
        Shipment shipment = createShipment(1L, ShipmentStatus.CREATED);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        assertThrows(ConflictException.class, () -> shipmentService.outbound(shipment.getId()));
    }

    // ==================== full happy-path state machine ====================

    @Test
    void fullHappyPath_createdToPickingToLabelPrintedToOutbound_succeeds() {
        Shipment shipment = createShipment(1L, ShipmentStatus.CREATED);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));
        when(pickListRepository.save(any(PickList.class))).thenAnswer(inv -> {
            PickList pl = inv.getArgument(0);
            pl.setId(10L);
            return pl;
        });
        when(labelRecordRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());

        shipmentService.pick(1L, 999L);
        assertEquals(ShipmentStatus.PICKING, shipment.getStatus());

        shipmentService.printLabel(1L, "SF");
        assertEquals(ShipmentStatus.LABEL_PRINTED, shipment.getStatus());

        shipmentService.outbound(1L);
        assertEquals(ShipmentStatus.OUTBOUND, shipment.getStatus());
    }

    // ==================== getShipmentByOrderId ====================

    @Test
    void testGetShipmentByOrderId_returnsShipment() {
        Shipment shipment = createShipment(1L, ShipmentStatus.OUTBOUND);
        shipment.setShipmentNo("SH202406010001");
        shipment.setOrderId(100L);
        shipment.setUserId(200L);
        shipment.setFreightAmount(new BigDecimal("8.00"));

        when(shipmentRepository.findByOrderId(100L)).thenReturn(Optional.of(shipment));
        when(trackingRepository.findByShipmentIdOrderByEventTimeAsc(1L))
                .thenReturn(Collections.emptyList());

        ShipmentResponse response = shipmentService.getShipmentByOrderId(100L);

        assertNotNull(response);
        assertEquals(1L, response.getId());
        assertEquals("SH202406010001", response.getShipmentNo());
        assertEquals(100L, response.getOrderId());
        assertEquals(200L, response.getUserId());
        assertEquals("OUTBOUND", response.getStatus());
        assertEquals(new BigDecimal("8.00"), response.getFreightAmount());
    }

    @Test
    void testGetShipmentByOrderId_notFound_throwsException() {
        when(shipmentRepository.findByOrderId(999L)).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class,
                () -> shipmentService.getShipmentByOrderId(999L));
    }

    // ==================== getShipmentByShipmentNo ====================

    @Test
    void testGetShipmentByShipmentNo_returnsShipment() {
        Shipment shipment = createShipment(2L, ShipmentStatus.IN_TRANSIT);
        shipment.setShipmentNo("SH202406010002");

        when(shipmentRepository.findByShipmentNo("SH202406010002"))
                .thenReturn(Optional.of(shipment));
        when(trackingRepository.findByShipmentIdOrderByEventTimeAsc(2L))
                .thenReturn(Collections.emptyList());

        ShipmentResponse response = shipmentService.getShipmentByShipmentNo("SH202406010002");

        assertNotNull(response);
        assertEquals("SH202406010002", response.getShipmentNo());
    }

    @Test
    void testGetShipmentByShipmentNo_notFound_throwsException() {
        when(shipmentRepository.findByShipmentNo("NONEXISTENT"))
                .thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class,
                () -> shipmentService.getShipmentByShipmentNo("NONEXISTENT"));
    }

    // ==================== updateStatus ====================

    @Test
    void testUpdateStatus_toCollected_setsPickupTime() {
        Shipment shipment = createShipment(1L, ShipmentStatus.OUTBOUND);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        shipmentService.updateStatus(1L, ShipmentStatus.COLLECTED,
                "Carrier Hub", "Package collected by carrier");

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        Shipment saved = captor.getValue();
        assertEquals(ShipmentStatus.COLLECTED, saved.getStatus());
        assertNotNull(saved.getPickupTime());
        verify(eventPublisher, never()).publish(any());
        // The single ShipmentTracking row for a carrier event is written by
        // LogisticsCallbackService.processCallback (with the carrier's
        // trackingNo/eventTime) — updateStatus itself must not write a second,
        // trackingNo-less duplicate.
        verify(trackingRepository, never()).save(any(ShipmentTracking.class));
    }

    @Test
    void testUpdateStatus_toDelivered_setsDeliveredAt() {
        Shipment shipment = createShipment(1L, ShipmentStatus.IN_TRANSIT);
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        shipmentService.updateStatus(1L, ShipmentStatus.DELIVERED,
                "Recipient Address", "Package delivered");

        ArgumentCaptor<Shipment> captor = ArgumentCaptor.forClass(Shipment.class);
        verify(shipmentRepository).save(captor.capture());
        Shipment saved = captor.getValue();
        assertEquals(ShipmentStatus.DELIVERED, saved.getStatus());
        assertNotNull(saved.getDeliveredAt());
    }

    @Test
    void updateStatus_toDelivered_publishesShipmentDeliveredEvent() {
        Shipment shipment = createShipment(1L, ShipmentStatus.IN_TRANSIT);
        Long orderId = shipment.getOrderId();
        when(shipmentRepository.findById(1L)).thenReturn(Optional.of(shipment));

        shipmentService.updateStatus(1L, ShipmentStatus.DELIVERED, "Shenzhen", "delivered");

        ArgumentCaptor<ShipmentDeliveredEvent> captor = ArgumentCaptor.forClass(ShipmentDeliveredEvent.class);
        verify(eventPublisher).publish(captor.capture());
        assertEquals(orderId, captor.getValue().getOrderId());
        assertEquals(1L, captor.getValue().getShipmentId());
        assertNotNull(captor.getValue().getDeliveredAt());
    }

    // ==================== helper ====================

    private Shipment createShipment(Long id, ShipmentStatus status) {
        Shipment shipment = new Shipment();
        shipment.setId(id);
        shipment.setShipmentNo("SH" + System.currentTimeMillis() + String.format("%04d", id));
        shipment.setOrderId(100L + id);
        shipment.setUserId(200L + id);
        shipment.setStatus(status);
        shipment.setFreightAmount(new BigDecimal("8.00"));
        shipment.setAddressSnapshot("{\"province\":\"Test\"}");
        return shipment;
    }
}
