package com.ecommerce.inventory.entity;

import com.ecommerce.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.persistence.Version;

@Entity
@Table(name = "inventory_stock", uniqueConstraints = {
        @UniqueConstraint(columnNames = { "warehouse_id", "sku_id" })
})
public class InventoryStock extends BaseEntity {

    @Column(name = "warehouse_id", nullable = false)
    private Long warehouseId;

    @Column(name = "sku_id", nullable = false)
    private Long skuId;

    @Column(name = "on_hand_stock")
    private int onHandStock;

    @Column(name = "reserved_stock")
    private int reservedStock;

    @Column(name = "safety_stock")
    private int safetyStock;

    /**
     * Low-stock warning threshold for this SKU/warehouse row (design-docs/附录C
     * inventory_stock.warning_threshold). Compared against onHandStock by
     * {@link com.ecommerce.inventory.service.StockWarningService#getWarnings()}
     * when positive. No frozen endpoint writes this column and inbound leaves it
     * at the schema default 0, so it only takes effect when data sets it directly.
     */
    @Column(name = "warning_threshold")
    private int warningThreshold;

    /**
     * Optimistic-locking version, guarding concurrent reserve()/release()/deductAfterPayment()
     * updates to the same row (design-docs/02 section 3 cross-module rules; see
     * InventoryReservationServiceImpl#reserve for the retry-once policy on conflict).
     */
    @Version
    @Column(name = "version")
    private Long version;

    public InventoryStock() {
    }

    /**
     * Returns the available stock: onHandStock minus reservedStock.
     */
    public int getAvailableStock() {
        return onHandStock - reservedStock;
    }

    public Long getWarehouseId() {
        return warehouseId;
    }

    public void setWarehouseId(Long warehouseId) {
        this.warehouseId = warehouseId;
    }

    public Long getSkuId() {
        return skuId;
    }

    public void setSkuId(Long skuId) {
        this.skuId = skuId;
    }

    public int getOnHandStock() {
        return onHandStock;
    }

    public void setOnHandStock(int onHandStock) {
        this.onHandStock = onHandStock;
    }

    public int getReservedStock() {
        return reservedStock;
    }

    public void setReservedStock(int reservedStock) {
        this.reservedStock = reservedStock;
    }

    public int getSafetyStock() {
        return safetyStock;
    }

    public void setSafetyStock(int safetyStock) {
        this.safetyStock = safetyStock;
    }

    public int getWarningThreshold() {
        return warningThreshold;
    }

    public void setWarningThreshold(int warningThreshold) {
        this.warningThreshold = warningThreshold;
    }

    public Long getVersion() {
        return version;
    }

    public void setVersion(Long version) {
        this.version = version;
    }
}
