package com.ecommerce.product.service;

import com.ecommerce.product.query.InventoryQueryService;
import com.ecommerce.product.query.StockSummaryDto;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Fetches stock info by delegating to the inventory module's {@link InventoryQueryService}.
 *
 * <p>The inventory module provides the runtime implementation of this
 * product-owned interface (design-docs/05 section 3: "库存摘要必须通过
 * InventoryQueryService.getStockSummary(skuId) 获取，不得直接访问库存表或注入库存模块 Repository").
 */
@Component
public class StockInfoFetcher {

    private static final Logger log = LoggerFactory.getLogger(StockInfoFetcher.class);

    private final InventoryQueryService inventoryQueryService;

    public StockInfoFetcher(InventoryQueryService inventoryQueryService) {
        this.inventoryQueryService = inventoryQueryService;
    }

    /**
     * Fetches stock info for a given SKU.
     *
     * @param skuId the SKU id
     * @return a stock summary
     */
    public StockSummaryDto fetch(Long skuId) {
        log.debug("StockInfoFetcher fetching stock for skuId={}", skuId);
        return inventoryQueryService.getStockSummary(skuId);
    }
}
