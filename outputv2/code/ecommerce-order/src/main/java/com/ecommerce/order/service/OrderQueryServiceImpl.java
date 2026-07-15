package com.ecommerce.order.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.order.dto.VerifyPurchaseResponse;
import com.ecommerce.order.entity.Order;
import com.ecommerce.order.entity.OrderItem;
import com.ecommerce.order.entity.OrderStatus;
import com.ecommerce.order.query.OrderDto;
import com.ecommerce.order.query.OrderPaymentStatusUpdater;
import com.ecommerce.order.query.OrderQueryService;
import com.ecommerce.order.repository.OrderItemRepository;
import com.ecommerce.order.repository.OrderRepository;
import com.ecommerce.product.query.ProductQueryService;
import com.ecommerce.product.query.SkuDto;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Implementation of {@link OrderQueryService} and {@link OrderPaymentStatusUpdater}.
 * This is the cross-module interface that other modules (payment, review, logistics, etc.)
 * use to query order data without accessing order repositories directly.
 *
 * <p>Per the architecture specification, the payment module MUST query orders
 * through this service and MUST NOT access order tables directly.
 */
@Service
@Transactional(readOnly = true)
public class OrderQueryServiceImpl implements OrderQueryService, OrderPaymentStatusUpdater {

    private static final Logger log = LoggerFactory.getLogger(OrderQueryServiceImpl.class);

    private final OrderRepository orderRepository;
    private final OrderItemRepository orderItemRepository;
    private final ProductQueryService productQueryService;
    private final OrderStateMachine stateMachine;
    private final DomainEventPublisher eventPublisher;

    public OrderQueryServiceImpl(OrderRepository orderRepository,
                                  OrderItemRepository orderItemRepository,
                                  ProductQueryService productQueryService,
                                  OrderStateMachine stateMachine,
                                  DomainEventPublisher eventPublisher) {
        this.orderRepository = orderRepository;
        this.orderItemRepository = orderItemRepository;
        this.productQueryService = productQueryService;
        this.stateMachine = stateMachine;
        this.eventPublisher = eventPublisher;
    }

    @Override
    public OrderDto getOrder(Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        return toDto(order);
    }

    @Override
    public OrderDto getPayableOrder(Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        // Only CREATED or PAYING orders can be paid
        if (order.getStatus() != OrderStatus.CREATED
                && order.getStatus() != OrderStatus.PAYING) {
            throw new ConflictException("ORDER_STATUS_CONFLICT",
                    "Order " + orderId + " is in status " + order.getStatus()
                            + " and cannot be paid");
        }
        return toDto(order);
    }

    @Override
    public VerifyPurchaseResponse verifyPurchase(Long userId, Long productId) {
        // Find delivered/completed orders for the user and check if product was purchased
        Page<Order> orders = orderRepository.findByUserId(userId,
                PageRequest.of(0, 200, Sort.by(Sort.Direction.DESC, "createdAt")));

        for (Order order : orders) {
            if (order.getStatus() != OrderStatus.DELIVERED
                    && order.getStatus() != OrderStatus.COMPLETED) {
                continue;
            }
            List<OrderItem> items = orderItemRepository.findByOrderId(order.getId());
            for (OrderItem item : items) {
                try {
                    // The verify-purchase contract's productId may be either the
                    // SPU id or the SKU id (see OrderFixture#verifyPurchase:
                    // "productId product (SPU/SKU) id"), so match on both.
                    SkuDto sku = productQueryService.getSku(item.getSkuId());
                    if (sku != null && (sku.getSpuId().equals(productId)
                            || item.getSkuId().equals(productId))) {
                        return new VerifyPurchaseResponse(true, order.getId(),
                                order.getUpdatedAt());
                    }
                } catch (Exception e) {
                    log.debug("Skipping skuId={} during purchase verification: {}",
                            item.getSkuId(), e.getMessage());
                }
            }
        }
        return new VerifyPurchaseResponse(false, null, null);
    }

    @Override
    public BigDecimal getOrderAmount(Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        return order.getPayableAmount();
    }

    // ======================== OrderPaymentStatusUpdater ========================

    @Override
    @Transactional
    public void markAsPaid(Long orderId, String paymentNo) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        OrderStatus fromStatus = order.getStatus();

        // Frozen contract (README §7.2): an order whose status does not allow the
        // operation is a status conflict — 409 ORDER_STATUS_CONFLICT — mirroring
        // getPayableOrder above. Guard explicitly here so a payment callback
        // arriving for a no-longer-payable order (e.g. CANCELLED meanwhile)
        // surfaces the frozen 409 code instead of the state machine's generic
        // ORDER_INVALID_TRANSITION 400 from deep inside the transition check.
        if (fromStatus != OrderStatus.CREATED && fromStatus != OrderStatus.PAYING) {
            throw new ConflictException("ORDER_STATUS_CONFLICT",
                    "Order " + orderId + " in status " + fromStatus
                            + " cannot be marked paid");
        }

        // Orders normally reach PAID via CREATED -> PAYING -> PAID, but nothing
        // in the current system drives the intermediate PAYING transition
        // before the (synchronous, mock) payment gateway confirms — payment's
        // OrderPaymentStatusUpdater contract only exposes markAsPaid/
        // markPaymentFailed, no "start paying" hook. So a CREATED order still
        // needs to be accepted here, but validated through the shared state
        // machine (both legal hops chained), never bypassed with an ad-hoc
        // status check.
        if (fromStatus == OrderStatus.CREATED) {
            stateMachine.validateTransition(OrderStatus.CREATED, OrderStatus.PAYING);
            stateMachine.validateTransition(OrderStatus.PAYING, OrderStatus.PAID);
        } else {
            stateMachine.validateTransition(fromStatus, OrderStatus.PAID);
        }

        order.setStatus(OrderStatus.PAID);
        order.setPaymentNo(paymentNo);
        order.setPaidAt(SystemClockService.now());
        order.setPaidAmount(order.getPayableAmount());
        orderRepository.save(order);

        log.info("Order {} marked as paid, paymentNo={}, amount={}",
                orderId, paymentNo, order.getPayableAmount());

        // Publish the shared OrderPaidEvent so logistics (auto-create shipment)
        // and loyalty (accrue points) — both of which only depend on
        // ecommerce-common, never on ecommerce-order — react to the payment.
        List<OrderItem> items = orderItemRepository.findByOrderId(orderId);
        eventPublisher.publish(new OrderPaidEvent(this, orderId, order.getUserId(),
                order.getPayableAmount(), toEventItems(items), String.valueOf(orderId), null));
    }

    @Override
    @Transactional
    public void markPaymentFailed(Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        if (order.getStatus() != OrderStatus.PAYING) {
            log.warn("Order {} is not in PAYING status, status is {} — ignoring payment failure",
                    orderId, order.getStatus());
            return;
        }

        // Revert to CREATED so the user can try paying again
        order.setStatus(OrderStatus.CREATED);
        orderRepository.save(order);

        log.info("Order {} payment failed, reverted to CREATED", orderId);
    }

    // ======================== Private helpers ========================

    private List<OrderPaidEvent.OrderItemPayload> toEventItems(List<OrderItem> items) {
        return items.stream()
                .map(item -> new OrderPaidEvent.OrderItemPayload(
                        item.getSkuId(), item.getQuantity(), item.getPrice()))
                .collect(Collectors.toList());
    }

    private OrderDto toDto(Order order) {
        OrderDto dto = new OrderDto();
        dto.setOrderId(order.getId());
        dto.setOrderNo(order.getOrderNo());
        dto.setUserId(order.getUserId());
        dto.setExternalOrderNo(order.getExternalOrderNo());
        dto.setStatus(order.getStatus());
        dto.setItemTotal(order.getItemTotal());
        dto.setShippingFee(order.getShippingFee());
        dto.setPackagingFee(order.getPackagingFee());
        dto.setDiscountAmount(order.getDiscountAmount());
        dto.setPointsDeductionAmount(order.getPointsDeductionAmount());
        dto.setPayableAmount(order.getPayableAmount());
        dto.setPaidAmount(order.getPaidAmount());
        dto.setAddressSnapshot(order.getAddressSnapshot());
        dto.setCouponIds(order.getCouponIds());
        dto.setRedeemedPoints(order.getRedeemedPoints());
        dto.setPaymentNo(order.getPaymentNo());
        dto.setCancelReason(order.getCancelReason());
        dto.setCreatedAt(order.getCreatedAt());
        dto.setPaidAt(order.getPaidAt());
        dto.setCancelledAt(order.getCancelledAt());
        dto.setExpiresAt(order.getExpiresAt());
        return dto;
    }
}
