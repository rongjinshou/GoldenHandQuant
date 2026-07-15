package com.ecommerce.inventory.service;

import com.ecommerce.inventory.dto.StockWarningResponse;
import com.ecommerce.inventory.entity.InventoryStock;
import com.ecommerce.inventory.entity.StockWarningRule;
import com.ecommerce.inventory.repository.InventoryStockRepository;
import com.ecommerce.inventory.repository.StockWarningRuleRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class StockWarningService {

    private static final Logger log = LoggerFactory.getLogger(StockWarningService.class);

    private final InventoryStockRepository inventoryStockRepository;
    private final StockWarningRuleRepository stockWarningRuleRepository;

    public StockWarningService(InventoryStockRepository inventoryStockRepository,
                               StockWarningRuleRepository stockWarningRuleRepository) {
        this.inventoryStockRepository = inventoryStockRepository;
        this.stockWarningRuleRepository = stockWarningRuleRepository;
    }

    /**
     * Returns all current low-stock warnings, combining two sources:
     *
     * <ol>
     *   <li>Rule-based: {@link StockWarningRule} rows set via the separate,
     *       non-contracted {@code POST .../warnings/rule} endpoint. Kept working
     *       as-is — additive, not replaced.</li>
     *   <li>Column-based: each {@link InventoryStock} row's own
     *       {@code warningThreshold} (design-docs/附录C inventory_stock.warning_threshold).
     *       Nothing in the frozen contract writes this column and inbound leaves it
     *       at the schema default 0, so this branch is naturally dormant (guarded by
     *       {@code > 0} below) unless data sets the column directly. With no rules
     *       and no column values, the endpoint correctly returns an empty list.</li>
     * </ol>
     *
     * <p>A given (warehouseId, skuId) row is only reported once even if it
     * matches both sources.
     */
    @Transactional(readOnly = true)
    public List<StockWarningResponse> getWarnings() {
        Map<String, StockWarningResponse> warningsByLocation = new LinkedHashMap<>();

        List<StockWarningRule> rules = stockWarningRuleRepository.findByEnabledTrue();
        for (StockWarningRule rule : rules) {
            List<InventoryStock> stocks;
            if (rule.getWarehouseId() != null) {
                stocks = inventoryStockRepository.findByWarehouseIdAndSkuId(
                        rule.getWarehouseId(), rule.getSkuId())
                        .map(List::of)
                        .orElse(List.of());
            } else {
                stocks = inventoryStockRepository.findBySkuId(rule.getSkuId());
            }

            for (InventoryStock stock : stocks) {
                if (stock.getOnHandStock() <= rule.getWarningThreshold()) {
                    addWarning(warningsByLocation, stock, rule.getWarningThreshold());
                }
            }
        }

        for (InventoryStock stock : inventoryStockRepository.findAll()) {
            if (stock.getWarningThreshold() > 0 && stock.getOnHandStock() <= stock.getWarningThreshold()) {
                addWarning(warningsByLocation, stock, stock.getWarningThreshold());
            }
        }

        log.debug("Stock warnings found: {}", warningsByLocation.size());
        return new ArrayList<>(warningsByLocation.values());
    }

    private void addWarning(Map<String, StockWarningResponse> warningsByLocation,
                            InventoryStock stock, int threshold) {
        String key = stock.getWarehouseId() + ":" + stock.getSkuId();
        if (warningsByLocation.containsKey(key)) {
            return;
        }
        StockWarningResponse response = new StockWarningResponse();
        response.setSkuId(stock.getSkuId());
        response.setWarehouseId(stock.getWarehouseId());
        response.setOnHandStock(stock.getOnHandStock());
        response.setSafetyStock(stock.getSafetyStock());
        response.setWarningThreshold(threshold);
        response.setMessage(String.format(
                "SKU %d in warehouse %d is below warning threshold: %d <= %d",
                stock.getSkuId(), stock.getWarehouseId(),
                stock.getOnHandStock(), threshold));
        warningsByLocation.put(key, response);
    }

    @Transactional
    public StockWarningRule setWarningRule(Long skuId, Long warehouseId, int warningThreshold) {
        StockWarningRule rule = stockWarningRuleRepository
                .findBySkuIdAndWarehouseId(skuId, warehouseId)
                .orElseGet(StockWarningRule::new);

        rule.setSkuId(skuId);
        rule.setWarehouseId(warehouseId);
        rule.setWarningThreshold(warningThreshold);
        rule.setEnabled(true);
        StockWarningRule saved = stockWarningRuleRepository.save(rule);
        log.info("Warning rule set: skuId={}, warehouseId={}, threshold={}",
                skuId, warehouseId, warningThreshold);
        return saved;
    }
}
