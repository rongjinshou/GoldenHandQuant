package com.ecommerce.product.service;

import com.ecommerce.product.query.InventoryQueryService;
import com.ecommerce.product.query.StockSummaryDto;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Per design-docs/05 section 3: "库存摘要必须通过 InventoryQueryService.getStockSummary(skuId)
 * 获取，不得直接访问库存表或注入库存模块 Repository." StockInfoFetcher previously ignored this and
 * returned a hardcoded StockSummaryDto(999, 0) for every SKU; it must instead delegate to the
 * real cross-module InventoryQueryService.
 */
@DisplayName("StockInfoFetcher")
@ExtendWith(MockitoExtension.class)
class StockInfoFetcherTest {

    @Mock
    private InventoryQueryService inventoryQueryService;

    private StockInfoFetcher stockInfoFetcher;

    @BeforeEach
    void setUp() {
        stockInfoFetcher = new StockInfoFetcher(inventoryQueryService);
    }

    @Test
    @DisplayName("fetch delegates to InventoryQueryService.getStockSummary and returns its result")
    void testFetch_delegatesToInventoryQueryService() {
        StockSummaryDto realSummary = new StockSummaryDto(42, 7);
        when(inventoryQueryService.getStockSummary(1L)).thenReturn(realSummary);

        StockSummaryDto result = stockInfoFetcher.fetch(1L);

        assertThat(result).isSameAs(realSummary);
        assertThat(result.getAvailableStock()).isEqualTo(42);
        assertThat(result.getReservedStock()).isEqualTo(7);
        verify(inventoryQueryService).getStockSummary(1L);
    }

    @Test
    @DisplayName("fetch reflects whatever the inventory module reports, not a hardcoded value")
    void testFetch_doesNotHardcodeStock() {
        when(inventoryQueryService.getStockSummary(2L)).thenReturn(new StockSummaryDto(0, 0));
        when(inventoryQueryService.getStockSummary(3L)).thenReturn(new StockSummaryDto(15, 3));

        assertThat(stockInfoFetcher.fetch(2L).getAvailableStock()).isZero();
        assertThat(stockInfoFetcher.fetch(3L).getAvailableStock()).isEqualTo(15);
    }
}
