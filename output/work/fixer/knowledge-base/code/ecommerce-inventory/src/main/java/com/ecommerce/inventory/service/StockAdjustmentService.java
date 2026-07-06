package com.ecommerce.inventory.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.inventory.entity.InventoryStock;
import com.ecommerce.inventory.entity.StockAdjustment;
import com.ecommerce.inventory.repository.InventoryStockRepository;
import com.ecommerce.inventory.repository.StockAdjustmentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class StockAdjustmentService {

    private static final Logger log = LoggerFactory.getLogger(StockAdjustmentService.class);

    private final InventoryStockRepository inventoryStockRepository;
    private final StockAdjustmentRepository stockAdjustmentRepository;
    private final AuditLogService auditLogService;

    public StockAdjustmentService(InventoryStockRepository inventoryStockRepository,
                                  StockAdjustmentRepository stockAdjustmentRepository,
                                  AuditLogService auditLogService) {
        this.inventoryStockRepository = inventoryStockRepository;
        this.stockAdjustmentRepository = stockAdjustmentRepository;
        this.auditLogService = auditLogService;
    }

    /**
     * Records a manual stock adjustment ("盘点调整"). Per design-docs/03 section 6,
     * manual inventory adjustment is one of the operations that must produce a
     * shared audit-log entry (operator, action type, business id, before/after
     * state, remark), in addition to the module-local {@link StockAdjustment} row.
     */
    @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
            cacheManager = "inventoryCacheManager")
    @Transactional
    public StockAdjustment create(Long warehouseId, Long skuId, int afterQty, String reason, String operatorId) {
        InventoryStock stock = inventoryStockRepository
                .findByWarehouseIdAndSkuId(warehouseId, skuId)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "InventoryStock", "warehouse=" + warehouseId + ", sku=" + skuId));

        int beforeQty = stock.getOnHandStock();
        stock.setOnHandStock(afterQty);
        inventoryStockRepository.save(stock);

        StockAdjustment adjustment = new StockAdjustment();
        adjustment.setWarehouseId(warehouseId);
        adjustment.setSkuId(skuId);
        adjustment.setBeforeQty(beforeQty);
        adjustment.setAfterQty(afterQty);
        adjustment.setReason(reason);
        adjustment.setOperatorId(operatorId);
        StockAdjustment saved = stockAdjustmentRepository.save(adjustment);

        auditLogService.record(operatorId, "INVENTORY_ADJUSTMENT", String.valueOf(skuId),
                String.valueOf(beforeQty), String.valueOf(afterQty), reason);

        log.info("Stock adjusted: warehouseId={}, skuId={}, {} -> {}, reason={}, operatorId={}",
                warehouseId, skuId, beforeQty, afterQty, reason, operatorId);
        return saved;
    }

    @Transactional(readOnly = true)
    public List<StockAdjustment> list(Long warehouseId) {
        return stockAdjustmentRepository.findByWarehouseId(warehouseId);
    }
}
