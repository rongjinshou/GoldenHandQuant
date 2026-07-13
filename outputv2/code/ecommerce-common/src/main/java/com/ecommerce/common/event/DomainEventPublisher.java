package com.ecommerce.common.event;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * Central publisher for domain events.
 * Wraps Spring's ApplicationEventPublisher and provides a uniform publish method.
 */
@Component
public class DomainEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(DomainEventPublisher.class);

    private final ApplicationEventPublisher applicationEventPublisher;
    private final FailedEventRecordRepository failedEventRecordRepository;
    private final ObjectMapper objectMapper;

    public DomainEventPublisher(ApplicationEventPublisher applicationEventPublisher,
                                FailedEventRecordRepository failedEventRecordRepository,
                                ObjectMapper objectMapper) {
        this.applicationEventPublisher = applicationEventPublisher;
        this.failedEventRecordRepository = failedEventRecordRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Publishes a domain event on the Spring application event bus.
     * If a listener throws an exception, it is caught, logged, and swallowed
     * so that non-critical listeners do not abort the main business transaction.
     *
     * @param event the domain event to publish
     */
    public void publish(AbstractDomainEvent event) {
        log.info("Publishing domain event: eventId={}, type={}, occurredAt={}",
                event.getEventId(), event.getClass().getSimpleName(), event.getOccurredAt());
        try {
            applicationEventPublisher.publishEvent(event);
            log.info("Domain event published successfully: eventId={}", event.getEventId());
        } catch (Exception e) {
            log.error("Failed to publish domain event: eventId={}, type={}, error={}",
                    event.getEventId(), event.getClass().getSimpleName(), e.getMessage(), e);
            persistFailure(event, e);
        }
    }

    /**
     * Persist a failure raised while a listener processed an event, so it becomes
     * visible via {@code GET /api/v1/admin/events/failures} (design-docs/03 §8).
     * Cross-module listeners deliberately swallow their exceptions (so a non-critical
     * listener failure never rolls back the main business transaction), and
     * AFTER_COMMIT listeners run after {@link #publish} has already returned — so
     * their failures never reach publish()'s own catch. Each such listener reports
     * here explicitly. Runs REQUIRES_NEW so the record commits even when the calling
     * listener's own transaction is being rolled back, and never throws (failing to
     * record must not turn a swallowed listener error into a hard error).
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordListenerFailure(Object event, String source, Throwable ex) {
        try {
            FailedEventRecord record = new FailedEventRecord();
            record.setEventType(event != null ? event.getClass().getSimpleName() : "UnknownEvent");
            String payload = "{}";
            if (event != null) {
                try {
                    payload = objectMapper.writeValueAsString(event);
                } catch (Exception ser) {
                    log.warn("Could not serialize failed event {}: {}",
                            event.getClass().getSimpleName(), ser.getMessage());
                }
            }
            record.setEventPayload(payload);
            record.setErrorMessage("[" + source + "] "
                    + (ex != null ? ex.getMessage() : "unknown error"));
            record.setOccurredAt(LocalDateTime.now());
            record.setRetried(false);
            record.setRetryCount(0);
            failedEventRecordRepository.save(record);
            log.warn("Recorded listener failure: event={}, source={}", record.getEventType(), source);
        } catch (Exception e) {
            log.error("Failed to persist listener failure record (source={}): {}", source, e.getMessage(), e);
        }
    }

    private void persistFailure(AbstractDomainEvent event, Exception exception) {
        try {
            FailedEventRecord record = new FailedEventRecord();
            record.setEventType(event.getClass().getSimpleName());
            record.setEventPayload(serializeEvent(event));
            record.setErrorMessage(exception.getMessage());
            record.setOccurredAt(LocalDateTime.now());
            record.setRetried(false);
            record.setRetryCount(0);
            failedEventRecordRepository.save(record);
        } catch (Exception e) {
            log.error("Failed to persist failed event record: {}", e.getMessage(), e);
        }
    }

    private String serializeEvent(AbstractDomainEvent event) {
        try {
            return objectMapper.writeValueAsString(event);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize domain event: eventId={}, type={}",
                    event.getEventId(), event.getClass().getSimpleName(), e);
            return "{}";
        }
    }
}
