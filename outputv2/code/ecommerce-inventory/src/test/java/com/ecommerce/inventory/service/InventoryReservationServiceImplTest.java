package com.ecommerce.inventory.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.inventory.entity.InventoryStock;
import com.ecommerce.inventory.entity.OutboundOrder;
import com.ecommerce.inventory.entity.ReservationStatus;
import com.ecommerce.inventory.entity.StockReservation;
import com.ecommerce.inventory.query.ReserveItem;
import com.ecommerce.inventory.repository.InventoryStockRepository;
import com.ecommerce.inventory.repository.OutboundOrderRepository;
import com.ecommerce.inventory.repository.StockReservationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.OptimisticLockingFailureException;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("InventoryReservationServiceImpl")
@ExtendWith(MockitoExtension.class)
class InventoryReservationServiceImplTest {

    @Mock
    private InventoryStockRepository stockRepo;

    @Mock
    private StockReservationRepository stockReservationRepo;

    @Mock
    private OutboundOrderRepository outboundOrderRepo;

    @InjectMocks
    private InventoryReservationServiceImpl reservationService;

    private InventoryStock stock;

    @BeforeEach
    void setUp() {
        stock = new InventoryStock();
        stock.setId(1L);
        stock.setWarehouseId(1L);
        stock.setSkuId(100L);
        stock.setOnHandStock(200);
        stock.setReservedStock(0);
        stock.setSafetyStock(5);
    }

    // ---- reserve tests ----

    @Test
    @DisplayName("reserve leaves onHandStock unchanged and only increases reservedStock")
    void testReserve_onlyIncreasesReservedStock_leavesOnHandStockUnchanged() {
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        List<ReserveItem> items = List.of(new ReserveItem(100L, 40));
        reservationService.reserve(1L, items);

        // onHandStock must stay untouched by reserve() (design-docs/06 section 3:
        // 校验库存可用 -> 创建 StockReservation -> 增加 reservedStock -> 不减少 onHandStock).
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        // reservedStock is correctly increased
        assertThat(stock.getReservedStock()).isEqualTo(40);
        // availableStock = onHandStock - reservedStock = 200 - 40 = 160
        assertThat(stock.getAvailableStock()).isEqualTo(160);
    }

    @Test
    @DisplayName("reserve distributes quantity across multiple warehouses")
    void testReserve_distributesAcrossWarehouses() {
        InventoryStock stock2 = new InventoryStock();
        stock2.setId(2L);
        stock2.setWarehouseId(2L);
        stock2.setSkuId(100L);
        stock2.setOnHandStock(50);
        stock2.setReservedStock(0);

        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock, stock2));
        when(stockRepo.saveAndFlush(any(InventoryStock.class))).thenAnswer(inv -> inv.getArgument(0));
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        List<ReserveItem> items = List.of(new ReserveItem(100L, 250));
        // First warehouse: max 200, reserves 200. Remaining: 50.
        // Second warehouse: max 50, reserves 50.
        reservationService.reserve(1L, items);

        // Warehouse 1: onHand stays 200 (unchanged), reserved = 200
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        assertThat(stock.getReservedStock()).isEqualTo(200);
        // Warehouse 2: onHand stays 50 (unchanged), reserved = 50
        assertThat(stock2.getOnHandStock()).isEqualTo(50);
        assertThat(stock2.getReservedStock()).isEqualTo(50);
    }

    @Test
    @DisplayName("reserve throws BusinessException when stock is insufficient")
    void testReserve_throwsWhenInsufficientStock() {
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));

        List<ReserveItem> items = List.of(new ReserveItem(100L, 300));

        assertThatThrownBy(() -> reservationService.reserve(1L, items))
                .isInstanceOf(BusinessException.class)
                .matches(ex -> ((BusinessException) ex).getCode().equals("INVENTORY_NOT_ENOUGH"),
                        "should have code INVENTORY_NOT_ENOUGH");
    }

    @Test
    @DisplayName("reserve skips warehouses with zero available stock")
    void testReserve_skipsZeroAvailableStock() {
        InventoryStock emptyStock = new InventoryStock();
        emptyStock.setId(2L);
        emptyStock.setWarehouseId(2L);
        emptyStock.setSkuId(100L);
        emptyStock.setOnHandStock(10);
        emptyStock.setReservedStock(10); // available = 0

        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(emptyStock, stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class))).thenAnswer(inv -> inv.getArgument(0));
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        List<ReserveItem> items = List.of(new ReserveItem(100L, 40));
        reservationService.reserve(1L, items);

        // emptyStock should be skipped (available=0) and left untouched
        assertThat(emptyStock.getOnHandStock()).isEqualTo(10);
        assertThat(emptyStock.getReservedStock()).isEqualTo(10);
        // stock should handle the full quantity; onHand unchanged, reserved increased
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        assertThat(stock.getReservedStock()).isEqualTo(40);
    }

    // ---- reserve concurrency-guard tests ----

    @Test
    @DisplayName("reserve retries once on optimistic lock conflict and succeeds against the freshly reloaded row")
    void testReserve_retriesOnceOnOptimisticLockConflict_thenSucceeds() {
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class)))
                .thenThrow(new OptimisticLockingFailureException("concurrent update"))
                .thenReturn(stock);

        // A concurrent transaction already reserved 20 units before our retry re-reads.
        InventoryStock freshStock = new InventoryStock();
        freshStock.setId(1L);
        freshStock.setWarehouseId(1L);
        freshStock.setSkuId(100L);
        freshStock.setOnHandStock(200);
        freshStock.setReservedStock(20);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(freshStock));
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        reservationService.reserve(1L, List.of(new ReserveItem(100L, 40)));

        // Retry re-applied the increment onto the freshly reloaded row (20 + 40).
        assertThat(freshStock.getReservedStock()).isEqualTo(60);
        verify(stockRepo, times(2)).saveAndFlush(any(InventoryStock.class));
    }

    @Test
    @DisplayName("reserve surfaces 409 ConflictException when the retry also conflicts")
    void testReserve_throwsConflictException_whenRetryAlsoConflicts() {
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class)))
                .thenThrow(new OptimisticLockingFailureException("conflict 1"))
                .thenThrow(new OptimisticLockingFailureException("conflict 2"));

        InventoryStock freshStock = new InventoryStock();
        freshStock.setId(1L);
        freshStock.setWarehouseId(1L);
        freshStock.setSkuId(100L);
        freshStock.setOnHandStock(200);
        freshStock.setReservedStock(20);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(freshStock));

        assertThatThrownBy(() -> reservationService.reserve(1L, List.of(new ReserveItem(100L, 40))))
                .isInstanceOf(ConflictException.class);

        verify(stockRepo, times(2)).saveAndFlush(any(InventoryStock.class));
    }

    @Test
    @DisplayName("reserve surfaces 409 ConflictException when the reloaded row no longer has enough stock")
    void testReserve_throwsConflictException_whenFreshStockInsufficientAfterConflict() {
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class)))
                .thenThrow(new OptimisticLockingFailureException("conflict"));

        // Concurrent transactions consumed nearly everything: only 10 left, need 40.
        InventoryStock freshStock = new InventoryStock();
        freshStock.setId(1L);
        freshStock.setWarehouseId(1L);
        freshStock.setSkuId(100L);
        freshStock.setOnHandStock(200);
        freshStock.setReservedStock(190);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(freshStock));

        assertThatThrownBy(() -> reservationService.reserve(1L, List.of(new ReserveItem(100L, 40))))
                .isInstanceOf(ConflictException.class);

        // Must not attempt a second write once the fresh read shows it can't fit.
        verify(stockRepo, times(1)).saveAndFlush(any(InventoryStock.class));
    }

    // ---- release tests ----

    @Test
    @DisplayName("release decreases reservedStock and does not touch onHandStock")
    void testRelease_decreasesReservedStock_leavesOnHandStockUnchanged() {
        // Simulate post-reserve state: onHandStock untouched by reserve(), reservedStock bumped.
        stock.setOnHandStock(200);
        stock.setReservedStock(40);

        StockReservation reservation = new StockReservation();
        reservation.setId(1L);
        reservation.setOrderId(1L);
        reservation.setSkuId(100L);
        reservation.setWarehouseId(1L);
        reservation.setQuantity(40);
        reservation.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(reservation));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        reservationService.release(1L);

        // reservedStock decreased to 0
        assertThat(stock.getReservedStock()).isEqualTo(0);
        // onHandStock was never touched by reserve() or release()
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        // availableStock = 200 - 0 = 200
        assertThat(stock.getAvailableStock()).isEqualTo(200);
        // reservation status updated to RELEASED
        assertThat(reservation.getStatus()).isEqualTo(ReservationStatus.RELEASED);
    }

    @Test
    @DisplayName("release throws ResourceNotFoundException when stock is missing")
    void testRelease_throwsWhenStockNotFound() {
        StockReservation reservation = new StockReservation();
        reservation.setId(1L);
        reservation.setOrderId(1L);
        reservation.setSkuId(100L);
        reservation.setWarehouseId(1L);
        reservation.setQuantity(40);
        reservation.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(reservation));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> reservationService.release(1L))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    @DisplayName("release does nothing when no RESERVED reservations exist")
    void testRelease_noReservedReservations_doesNothing() {
        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of());
        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.DEDUCTED))
                .thenReturn(List.of());

        reservationService.release(1L);

        verify(stockRepo, never()).save(any());
        verify(stockReservationRepo, never()).save(any());
    }

    @Test
    @DisplayName("release restores onHandStock for an already-DEDUCTED reservation "
            + "(PAID order cancel-review approved after post-payment deduction)")
    void testRelease_deductedReservation_restoresOnHandStock() {
        // Simulate post-deduction state: onHandStock already decreased by deductAfterPayment.
        stock.setOnHandStock(150); // was 200, 50 already deducted
        stock.setReservedStock(0);

        StockReservation deducted = new StockReservation();
        deducted.setId(1L);
        deducted.setOrderId(1L);
        deducted.setSkuId(100L);
        deducted.setWarehouseId(1L);
        deducted.setQuantity(50);
        deducted.setStatus(ReservationStatus.DEDUCTED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of());
        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.DEDUCTED))
                .thenReturn(List.of(deducted));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));

        reservationService.release(1L);

        assertThat(stock.getOnHandStock()).isEqualTo(200); // 150 + 50 restored
        assertThat(deducted.getStatus()).isEqualTo(ReservationStatus.RELEASED);
    }

    // ---- deductAfterPayment tests ----

    @Test
    @DisplayName("deductAfterPayment decreases both onHandStock and reservedStock")
    void testDeductAfterPayment_adjustsBothStocks() {
        // Simulate post-reserve state: onHandStock untouched by reserve(), reservedStock bumped.
        stock.setOnHandStock(200);
        stock.setReservedStock(40);

        StockReservation reservation = new StockReservation();
        reservation.setId(1L);
        reservation.setOrderId(1L);
        reservation.setSkuId(100L);
        reservation.setWarehouseId(1L);
        reservation.setQuantity(40);
        reservation.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(reservation));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));
        when(outboundOrderRepo.save(any(OutboundOrder.class))).thenAnswer(inv -> inv.getArgument(0));

        reservationService.deductAfterPayment(1L);

        // onHandStock: 200 - 40 = 160 (deductAfterPayment is the only place this ever
        // decreases now that reserve() no longer touches onHandStock)
        assertThat(stock.getOnHandStock()).isEqualTo(160);
        // reservedStock: 40 - 40 = 0
        assertThat(stock.getReservedStock()).isEqualTo(0);
        // availableStock = 160 - 0 = 160
        assertThat(stock.getAvailableStock()).isEqualTo(160);
        // reservation status updated to DEDUCTED
        assertThat(reservation.getStatus()).isEqualTo(ReservationStatus.DEDUCTED);
    }

    @Test
    @DisplayName("deductAfterPayment throws ResourceNotFoundException when stock is missing")
    void testDeductAfterPayment_throwsWhenStockNotFound() {
        StockReservation reservation = new StockReservation();
        reservation.setId(1L);
        reservation.setOrderId(1L);
        reservation.setSkuId(100L);
        reservation.setWarehouseId(1L);
        reservation.setQuantity(40);
        reservation.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(reservation));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> reservationService.deductAfterPayment(1L))
                .isInstanceOf(ResourceNotFoundException.class);

        verify(outboundOrderRepo, never()).save(any());
    }

    @Test
    @DisplayName("deductAfterPayment creates an OutboundOrder with COMPLETED status for each reservation")
    void testDeductAfterPayment_createsOutboundOrderForEachReservation() {
        // Arrange a reservation exactly as the tests above do.
        stock.setOnHandStock(200);
        stock.setReservedStock(40);

        StockReservation reservation = new StockReservation();
        reservation.setId(1L);
        reservation.setOrderId(1L);
        reservation.setSkuId(100L);
        reservation.setWarehouseId(1L);
        reservation.setQuantity(40);
        reservation.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(reservation));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));
        when(outboundOrderRepo.save(any(OutboundOrder.class))).thenAnswer(inv -> inv.getArgument(0));

        reservationService.deductAfterPayment(1L);

        ArgumentCaptor<OutboundOrder> captor = ArgumentCaptor.forClass(OutboundOrder.class);
        verify(outboundOrderRepo).save(captor.capture());
        OutboundOrder outboundOrder = captor.getValue();
        assertThat(outboundOrder.getWarehouseId()).isEqualTo(1L);
        assertThat(outboundOrder.getSkuId()).isEqualTo(100L);
        assertThat(outboundOrder.getQuantity()).isEqualTo(40);
        assertThat(outboundOrder.getOrderId()).isEqualTo(1L);
        assertThat(outboundOrder.getStatus()).isEqualTo("COMPLETED");
        assertThat(outboundOrder.getOrderNo()).startsWith("OB");
    }

    // ---- full cycle test ----

    @Test
    @DisplayName("full reserve-release-deduct cycle produces correct final state")
    void testFullReserveReleaseDeductCycle() {
        // ---- Setup: stock with 200 on-hand, 0 reserved ----
        when(stockRepo.findBySkuId(100L)).thenReturn(List.of(stock));
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.saveAndFlush(any(InventoryStock.class))).thenReturn(stock);
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(stockReservationRepo.save(any(StockReservation.class)))
                .thenAnswer(inv -> inv.getArgument(0));
        when(outboundOrderRepo.save(any(OutboundOrder.class))).thenAnswer(inv -> inv.getArgument(0));

        // Reservations for orderId=1 (created during first reserve)
        StockReservation res1 = new StockReservation();
        res1.setId(1L);
        res1.setOrderId(1L);
        res1.setSkuId(100L);
        res1.setWarehouseId(1L);
        res1.setQuantity(50);
        res1.setStatus(ReservationStatus.RESERVED);

        // Reservations for orderId=2 (created during second reserve)
        StockReservation res2 = new StockReservation();
        res2.setId(2L);
        res2.setOrderId(2L);
        res2.setSkuId(100L);
        res2.setWarehouseId(1L);
        res2.setQuantity(50);
        res2.setStatus(ReservationStatus.RESERVED);

        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.RESERVED))
                .thenReturn(List.of(res1));
        when(stockReservationRepo.findByOrderIdAndStatus(2L, ReservationStatus.RESERVED))
                .thenReturn(List.of(res2));
        // release() also checks for already-DEDUCTED reservations (a PAID order's
        // cancel-review path) — none here, orderId=1 is still RESERVED at release time
        // (only release(1L) is exercised below; orderId=2 goes reserve->deduct, no release).
        when(stockReservationRepo.findByOrderIdAndStatus(1L, ReservationStatus.DEDUCTED))
                .thenReturn(List.of());

        // ---- Step 1: Reserve orderId=1, quantity=50 ----
        reservationService.reserve(1L, List.of(new ReserveItem(100L, 50)));

        // onHandStock unchanged by reserve()
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        assertThat(stock.getReservedStock()).isEqualTo(50);
        assertThat(stock.getAvailableStock()).isEqualTo(150); // 200 - 50

        // ---- Step 2: Release orderId=1 ----
        reservationService.release(1L);

        // reservedStock back to 0; onHandStock still untouched
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        assertThat(stock.getReservedStock()).isEqualTo(0);
        assertThat(stock.getAvailableStock()).isEqualTo(200); // 200 - 0
        assertThat(res1.getStatus()).isEqualTo(ReservationStatus.RELEASED);

        // ---- Step 3: Reserve orderId=2, quantity=50 ----
        reservationService.reserve(2L, List.of(new ReserveItem(100L, 50)));

        // onHandStock still unchanged; reservedStock increases again
        assertThat(stock.getOnHandStock()).isEqualTo(200);
        assertThat(stock.getReservedStock()).isEqualTo(50);
        assertThat(stock.getAvailableStock()).isEqualTo(150); // 200 - 50

        // ---- Step 4: Deduct after payment for orderId=2 ----
        reservationService.deductAfterPayment(2L);

        // deductAfterPayment is the only operation that ever decreases onHandStock.
        assertThat(stock.getOnHandStock()).isEqualTo(150); // 200 - 50
        assertThat(stock.getReservedStock()).isEqualTo(0); // 50 - 50
        assertThat(stock.getAvailableStock()).isEqualTo(150); // 150 - 0
        assertThat(res2.getStatus()).isEqualTo(ReservationStatus.DEDUCTED);
    }
}
