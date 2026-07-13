package com.ecommerce.app.controller;

import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.exception.ValidationException;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.common.test.SystemClockService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Map;

/**
 * Test-support endpoints for the black-box harness: runtime configuration
 * ({@code /configs/**}) and system-clock control ({@code /clock}).
 *
 * <p>This controller intentionally exposes <em>no</em> database reset or admin
 * bootstrap endpoint. Per design-docs/03 §5, black-box isolation is provided by
 * the test harness (a fresh Spring context + random H2 per case); business code
 * must not ship its own reset/bootstrap hooks. The former {@code reset-sandbox}
 * and {@code bootstrap-admin} endpoints were unauthenticated ({@code permitAll})
 * and let any caller wipe the database or mint an ADMIN token, so they have been
 * removed along with their security rules.
 */
@RestController
@RequestMapping("/api/v1/admin/system")
public class SystemAdminController {

    private static final Logger log = LoggerFactory.getLogger(SystemAdminController.class);

    @PutMapping("/configs/{key}")
    public ResponseEntity<Map<String, Object>> putConfig(@PathVariable String key,
                                                          @RequestBody Map<String, Object> body) {
        Object value = body.get("value");
        if (value == null) {
            // Standard contract error body (400 VALIDATION_FAILED) instead of an
            // ad-hoc {"error": ...} map — design-docs/03 fixes the error shape to
            // {code, message, traceId, details} for every endpoint, and per
            // design-docs/01 the test-support endpoints are part of the API contract.
            throw new ValidationException("value is required");
        }
        RuntimeConfigRegistry.put(key, value);
        log.info("Config set: {} = {}", key, value);
        return ResponseEntity.ok(Map.of("key", key, "value", value));
    }

    @GetMapping("/configs/{key}")
    public ResponseEntity<Map<String, Object>> getConfig(@PathVariable String key) {
        Object value = RuntimeConfigRegistry.getOrDefault(key);
        if (value == null) {
            // 404 with the RESOURCE_NOT_FOUND contract body (README §7.1), not an
            // empty-body ResponseEntity.notFound().
            throw new ResourceNotFoundException("Config not found: " + key);
        }
        return ResponseEntity.ok(Map.of("key", key, "value", value));
    }

    @PutMapping("/clock")
    public ResponseEntity<Map<String, Object>> setClock(@RequestBody Map<String, Object> body) {
        if (body.containsKey("offsetMinutes")) {
            long offset = parseOffsetMinutes(body.get("offsetMinutes"));
            SystemClockService.setOffset(offset);
            log.info("Clock offset set to {} minutes", offset);
            return ResponseEntity.ok(Map.of("offsetMinutes", offset));
        } else if (body.containsKey("timestamp")) {
            String timestamp = String.valueOf(body.get("timestamp"));
            try {
                LocalDateTime fixed = LocalDateTime.parse(timestamp, DateTimeFormatter.ISO_LOCAL_DATE_TIME);
                SystemClockService.setFixed(fixed);
                log.info("Clock fixed at {}", fixed);
                return ResponseEntity.ok(Map.of("timestamp", fixed.toString()));
            } catch (DateTimeParseException e) {
                throw new ValidationException("Invalid timestamp format, use ISO_LOCAL_DATE_TIME");
            }
        }
        throw new ValidationException("Either offsetMinutes or timestamp is required");
    }

    /**
     * Defensive parse of the {@code offsetMinutes} body field: accepts a JSON
     * number or a numeric string. Anything else is a client error (400
     * VALIDATION_FAILED through the standard error body) — the previous blind
     * {@code (Number)} cast turned a string payload into a 500.
     */
    private static long parseOffsetMinutes(Object raw) {
        if (raw instanceof Number number) {
            return number.longValue();
        }
        try {
            return Long.parseLong(String.valueOf(raw).trim());
        } catch (NumberFormatException e) {
            throw new ValidationException("offsetMinutes must be an integer number of minutes");
        }
    }

    @DeleteMapping("/clock")
    public ResponseEntity<Map<String, Object>> resetClock() {
        SystemClockService.reset();
        log.info("Clock reset to system time");
        return ResponseEntity.ok(Map.of("reset", true));
    }
}
