package com.ecommerce.inventory.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.inventory.entity.InventoryStock;
import com.ecommerce.inventory.entity.OutboundOrder;
import com.ecommerce.inventory.entity.ReservationStatus;
import com.ecommerce.inventory.entity.StockReservation;
import com.ecommerce.inventory.query.InventoryReservationService;
import com.ecommerce.inventory.query.ReserveItem;
import com.ecommerce.inventory.repository.InventoryStockRepository;
import com.ecommerce.inventory.repository.OutboundOrderRepository;
import com.ecommerce.inventory.repository.StockReservationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * Handles stock reservation, release, and deduction during the order lifecycle.
 */
@Service
public class InventoryReservationServiceImpl implements InventoryReservationService {

    private static final Logger log = LoggerFactory.getLogger(InventoryReservationServiceImpl.class);

    private final InventoryStockRepository inventoryStockRepository;
    private final StockReservationRepository stockReservationRepository;
    private final OutboundOrderRepository outboundOrderRepository;

    public InventoryReservationServiceImpl(InventoryStockRepository inventoryStockRepository,
                                           StockReservationRepository stockReservationRepository,
                                           OutboundOrderRepository outboundOrderRepository) {
        this.inventoryStockRepository = inventoryStockRepository;
        this.stockReservationRepository = stockReservationRepository;
        this.outboundOrderRepository = outboundOrderRepository;
    }

    @Override
    @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
            cacheManager = "inventoryCacheManager")
    @Transactional
    public void reserve(Long orderId, List<ReserveItem> items) {
        for (ReserveItem item : items) {
            List<InventoryStock> stocks = inventoryStockRepository.findBySkuId(item.getSkuId());
            int remaining = item.getQuantity();

            for (InventoryStock stock : stocks) {
                if (remaining <= 0) {
                    break;
                }
                int available = stock.getAvailableStock();
                if (available <= 0) {
                    continue;
                }
                int toReserve = Math.min(remaining, available);

                // Reservation only ever increments reservedStock. onHandStock is
                // physical stock on the shelf and must stay untouched until
                // deductAfterPayment() actually ships it (design-docs/06 section 3):
                //   校验库存可用 -> 创建 StockReservation -> 增加 reservedStock -> 不减少 onHandStock
                reserveWithOptimisticRetry(stock, toReserve);

                StockReservation reservation = new StockReservation();
                reservation.setOrderId(orderId);
                reservation.setSkuId(item.getSkuId());
                reservation.setWarehouseId(stock.getWarehouseId());
                reservation.setQuantity(toReserve);
                reservation.setStatus(ReservationStatus.RESERVED);
                reservation.setExpiresAt(LocalDateTime.now().plusMinutes(30));
                stockReservationRepository.save(reservation);

                remaining -= toReserve;
            }

            if (remaining > 0) {
                throw new BusinessException("INSUFFICIENT_STOCK",
                        "Not enough available stock for skuId=" + item.getSkuId()
                                + ", shortage=" + remaining);
            }
        }
        log.info("Stock reserved for orderId={}, itemsCount={}", orderId, items.size());
    }

    /**
     * Applies the reservedStock increment for one (warehouse, SKU) row and flushes
     * immediately so a concurrent reserve/release/deduct on the same row surfaces
     * as an {@link OptimisticLockingFailureException} here (guarded by
     * {@link InventoryStock#getVersion()}) rather than silently overselling or
     * surfacing later as an unhandled 500 at transaction commit.
     *
     * <p>On conflict, reloads the row once and retries with the freshly-read
     * availableStock; if that still can't fit toReserve, or conflicts again, the
     * reservation is refused with 409 via {@link ConflictException} rather than
     * being retried indefinitely.
     */
    private void reserveWithOptimisticRetry(InventoryStock stock, int toReserve) {
        try {
            stock.setReservedStock(stock.getReservedStock() + toReserve);
            inventoryStockRepository.saveAndFlush(stock);
        } catch (OptimisticLockingFailureException ex) {
            InventoryStock fresh = inventoryStockRepository
                    .findByWarehouseIdAndSkuId(stock.getWarehouseId(), stock.getSkuId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "InventoryStock not found while retrying reserve"));

            if (fresh.getAvailableStock() < toReserve) {
                throw new ConflictException(
                        "Concurrent stock update left insufficient stock for skuId=" + stock.getSkuId()
                                + " in warehouseId=" + stock.getWarehouseId());
            }

            try {
                fresh.setReservedStock(fresh.getReservedStock() + toReserve);
                inventoryStockRepository.saveAndFlush(fresh);
            } catch (OptimisticLockingFailureException ex2) {
                throw new ConflictException(
                        "Concurrent stock update conflict for skuId=" + stock.getSkuId()
                                + " in warehouseId=" + stock.getWarehouseId() + "; please retry the request");
            }
        }
    }

    @Override
    @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
            cacheManager = "inventoryCacheManager")
    @Transactional
    public void release(Long orderId) {
        List<StockReservation> reservations = stockReservationRepository
                .findByOrderIdAndStatus(orderId, ReservationStatus.RESERVED);

        for (StockReservation reservation : reservations) {
            InventoryStock stock = inventoryStockRepository
                    .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "InventoryStock not found for release"));

            stock.setReservedStock(stock.getReservedStock() - reservation.getQuantity());
            inventoryStockRepository.save(stock);

            reservation.setStatus(ReservationStatus.RELEASED);
            stockReservationRepository.save(reservation);
        }
        log.info("Stock released for orderId={}, reservationsCount={}", orderId, reservations.size());
    }

    @Override
    @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
            cacheManager = "inventoryCacheManager")
    @Transactional
    public void deductAfterPayment(Long orderId) {
        List<StockReservation> reservations = stockReservationRepository
                .findByOrderIdAndStatus(orderId, ReservationStatus.RESERVED);

        for (StockReservation reservation : reservations) {
            InventoryStock stock = inventoryStockRepository
                    .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "InventoryStock not found for deduction"));

            stock.setOnHandStock(stock.getOnHandStock() - reservation.getQuantity());
            stock.setReservedStock(stock.getReservedStock() - reservation.getQuantity());
            inventoryStockRepository.save(stock);

            reservation.setStatus(ReservationStatus.DEDUCTED);
            stockReservationRepository.save(reservation);

            // design-docs/06 section 3: 支付成功后扣减库存 ... -> 生成 OutboundOrder.
            // Mirrors InventoryService.outbound()'s manual-outbound field set exactly.
            OutboundOrder outboundOrder = new OutboundOrder();
            outboundOrder.setOrderNo("OB" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss")));
            outboundOrder.setWarehouseId(reservation.getWarehouseId());
            outboundOrder.setSkuId(reservation.getSkuId());
            outboundOrder.setQuantity(reservation.getQuantity());
            outboundOrder.setOrderId(orderId);
            outboundOrder.setStatus("COMPLETED");
            outboundOrderRepository.save(outboundOrder);
        }
        log.info("Stock deducted after payment for orderId={}, reservationsCount={}",
                orderId, reservations.size());
    }
}
