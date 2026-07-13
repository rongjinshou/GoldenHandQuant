package com.ecommerce.common.event;

import org.springframework.context.ApplicationEvent;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Base class for all domain events in the ShopHub system.
 * Extends Spring's ApplicationEvent for integration with the Spring event bus.
 */
public abstract class AbstractDomainEvent extends ApplicationEvent {

    private final String eventId;
    private final LocalDateTime occurredAt;
    private final String aggregateId;
    private final String traceId;

    public AbstractDomainEvent(Object source) {
        this(source, null, null);
    }

    protected AbstractDomainEvent(Object source, String aggregateId, String traceId) {
        super(source);
        this.eventId = UUID.randomUUID().toString();
        this.occurredAt = LocalDateTime.now();
        this.aggregateId = aggregateId;
        this.traceId = traceId;
    }

    public String getEventId() {
        return eventId;
    }

    public LocalDateTime getOccurredAt() {
        return occurredAt;
    }

    public String getAggregateId() {
        return aggregateId;
    }

    public String getTraceId() {
        return traceId;
    }

    public String getEventType() {
        return getClass().getSimpleName();
    }
}
