package com.ecommerce.inventory.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.inventory.entity.InventoryStock;
import com.ecommerce.inventory.entity.StockAdjustment;
import com.ecommerce.inventory.repository.InventoryStockRepository;
import com.ecommerce.inventory.repository.StockAdjustmentRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("StockAdjustmentService")
@ExtendWith(MockitoExtension.class)
class StockAdjustmentServiceTest {

    @Mock
    private InventoryStockRepository stockRepo;

    @Mock
    private StockAdjustmentRepository adjustmentRepo;

    @Mock
    private AuditLogService auditLogService;

    @InjectMocks
    private StockAdjustmentService adjustmentService;

    @Test
    @DisplayName("create adjusts stock to afterQty and saves adjustment with before, after quantities and operator")
    void testCreate_createsAdjustment() {
        InventoryStock stock = new InventoryStock();
        stock.setId(1L);
        stock.setWarehouseId(1L);
        stock.setSkuId(100L);
        stock.setOnHandStock(100);
        stock.setReservedStock(0);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(adjustmentRepo.save(any(StockAdjustment.class))).thenAnswer(inv -> {
            StockAdjustment a = inv.getArgument(0);
            a.setId(1L);
            return a;
        });

        StockAdjustment result = adjustmentService.create(1L, 100L, 80, "Physical inventory count", "admin-1");

        // Stock adjusted correctly
        assertThat(stock.getOnHandStock()).isEqualTo(80);

        // Adjustment record created, including the operator who made it
        assertThat(result.getId()).isEqualTo(1L);
        assertThat(result.getWarehouseId()).isEqualTo(1L);
        assertThat(result.getSkuId()).isEqualTo(100L);
        assertThat(result.getBeforeQty()).isEqualTo(100);
        assertThat(result.getAfterQty()).isEqualTo(80);
        assertThat(result.getReason()).isEqualTo("Physical inventory count");
        assertThat(result.getOperatorId()).isEqualTo("admin-1");
    }

    @Test
    @DisplayName("create records a shared audit-log entry for the manual inventory adjustment "
            + "(design-docs/03 section 6: 库存人工调整)")
    void testCreate_recordsAuditLogEntry() {
        InventoryStock stock = new InventoryStock();
        stock.setId(1L);
        stock.setWarehouseId(1L);
        stock.setSkuId(100L);
        stock.setOnHandStock(100);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(adjustmentRepo.save(any(StockAdjustment.class))).thenAnswer(inv -> inv.getArgument(0));

        adjustmentService.create(1L, 100L, 80, "Physical inventory count", "admin-1");

        verify(auditLogService).record("admin-1", "INVENTORY_ADJUSTMENT", "100", "100", "80",
                "Physical inventory count");
    }

    @Test
    @DisplayName("create increases stock when afterQty is greater than beforeQty")
    void testCreate_increasesStock() {
        InventoryStock stock = new InventoryStock();
        stock.setId(1L);
        stock.setWarehouseId(1L);
        stock.setSkuId(100L);
        stock.setOnHandStock(50);

        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.of(stock));
        when(stockRepo.save(any(InventoryStock.class))).thenReturn(stock);
        when(adjustmentRepo.save(any(StockAdjustment.class))).thenAnswer(inv -> {
            StockAdjustment a = inv.getArgument(0);
            a.setId(2L);
            return a;
        });

        StockAdjustment result = adjustmentService.create(1L, 100L, 150, "Stock increase", "admin-2");

        assertThat(stock.getOnHandStock()).isEqualTo(150);
        assertThat(result.getBeforeQty()).isEqualTo(50);
        assertThat(result.getAfterQty()).isEqualTo(150);
    }

    @Test
    @DisplayName("create throws ResourceNotFoundException when stock does not exist")
    void testCreate_throwsWhenStockNotFound() {
        when(stockRepo.findByWarehouseIdAndSkuId(1L, 100L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> adjustmentService.create(1L, 100L, 80, "reason", "admin-1"))
                .isInstanceOf(ResourceNotFoundException.class);

        verify(auditLogService, never()).record(any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("list returns all adjustments for a warehouse")
    void testList_returnsAdjustmentsForWarehouse() {
        StockAdjustment adj1 = new StockAdjustment();
        adj1.setId(1L);
        adj1.setWarehouseId(1L);
        adj1.setSkuId(100L);
        adj1.setBeforeQty(100);
        adj1.setAfterQty(80);
        adj1.setReason("Count 1");

        StockAdjustment adj2 = new StockAdjustment();
        adj2.setId(2L);
        adj2.setWarehouseId(1L);
        adj2.setSkuId(200L);
        adj2.setBeforeQty(50);
        adj2.setAfterQty(60);
        adj2.setReason("Count 2");

        when(adjustmentRepo.findByWarehouseId(1L)).thenReturn(List.of(adj1, adj2));

        List<StockAdjustment> result = adjustmentService.list(1L);

        assertThat(result).hasSize(2);
        assertThat(result).extracting(StockAdjustment::getReason)
                .containsExactly("Count 1", "Count 2");
        verify(adjustmentRepo).findByWarehouseId(1L);
    }

    @Test
    @DisplayName("list returns empty list when no adjustments exist for warehouse")
    void testList_returnsEmptyWhenNoAdjustments() {
        when(adjustmentRepo.findByWarehouseId(999L)).thenReturn(List.of());

        List<StockAdjustment> result = adjustmentService.list(999L);

        assertThat(result).isEmpty();
    }
}
