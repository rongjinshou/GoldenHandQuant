package com.ecommerce.order.service;

import com.ecommerce.order.dto.BatchCreateOrderRequest;
import com.ecommerce.order.dto.BatchCreateOrderResponse;
import com.ecommerce.order.dto.BatchCreateOrderResponse.BatchOrderResult;
import com.ecommerce.order.dto.CreateOrderRequest;
import com.ecommerce.order.dto.CreateOrderResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * Service for batch order creation (e.g., for import or migration scenarios).
 *
 * <p>Deliberately NOT {@code @Transactional} at the class or method level:
 * per design-docs/08 §7 ("任何一条失败不得导致整批订单回滚"), one order's
 * failure must not roll back the others in the batch. Each
 * {@link #createBatch} iteration calls {@code orderService.createOrder(...)}
 * on a separately-injected Spring bean, so each call runs in and commits its
 * own independent transaction through {@code OrderService}'s own
 * {@code @Transactional} proxy — not a single shared transaction.
 */
@Service
public class BatchOrderService {

    private static final Logger log = LoggerFactory.getLogger(BatchOrderService.class);

    private final OrderService orderService;

    public BatchOrderService(OrderService orderService) {
        this.orderService = orderService;
    }

    /**
     * Create multiple orders in a batch.
     *
     * @param userId  the user creating the batch
     * @param request the batch request containing multiple orders
     * @return the batch result with per-order success/failure
     */
    public BatchCreateOrderResponse createBatch(Long userId, BatchCreateOrderRequest request) {
        log.info("Processing batch of {} orders for userId={}, continueOnError={}",
                request.getOrders().size(), userId, request.isContinueOnError());

        List<BatchOrderResult> results = new ArrayList<>();
        int successCount = 0;
        int failureCount = 0;

        for (CreateOrderRequest orderRequest : request.getOrders()) {
            try {
                CreateOrderResponse response = orderService.createOrder(userId, orderRequest);
                results.add(BatchOrderResult.success(
                        orderRequest.getExternalOrderNo(),
                        response.getOrderId(),
                        response.getOrderNo()));
                successCount++;
                log.debug("Batch order created: externalOrderNo={}, orderId={}",
                        orderRequest.getExternalOrderNo(), response.getOrderId());
            } catch (Exception e) {
                log.warn("Batch order failed: externalOrderNo={}, error={}",
                        orderRequest.getExternalOrderNo(), e.getMessage());
                results.add(BatchOrderResult.failure(
                        orderRequest.getExternalOrderNo(), e.getMessage()));
                failureCount++;
                // design-docs/08 §7: invalid orders are recorded and SKIPPED; a
                // single failure must never abort/roll back the batch. Always
                // continue so every row gets a per-order result (the request's
                // continueOnError flag is not part of the frozen contract).
            }
        }

        BatchCreateOrderResponse response = new BatchCreateOrderResponse();
        response.setTotalCount(results.size());
        response.setSuccessCount(successCount);
        response.setFailureCount(failureCount);
        response.setResults(results);

        log.info("Batch processing complete: total={}, success={}, failure={}",
                results.size(), successCount, failureCount);

        return response;
    }
}
