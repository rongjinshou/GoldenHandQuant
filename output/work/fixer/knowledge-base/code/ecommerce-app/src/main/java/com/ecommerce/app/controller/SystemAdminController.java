package com.ecommerce.app.controller;

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
            return ResponseEntity.badRequest().body(Map.of("error", "value is required"));
        }
        RuntimeConfigRegistry.put(key, value);
        log.info("Config set: {} = {}", key, value);
        return ResponseEntity.ok(Map.of("key", key, "value", value));
    }

    @GetMapping("/configs/{key}")
    public ResponseEntity<Map<String, Object>> getConfig(@PathVariable String key) {
        Object value = RuntimeConfigRegistry.getOrDefault(key);
        if (value == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(Map.of("key", key, "value", value));
    }

    @PutMapping("/clock")
    public ResponseEntity<Map<String, Object>> setClock(@RequestBody Map<String, Object> body) {
        if (body.containsKey("offsetMinutes")) {
            long offset = ((Number) body.get("offsetMinutes")).longValue();
            SystemClockService.setOffset(offset);
            log.info("Clock offset set to {} minutes", offset);
            return ResponseEntity.ok(Map.of("offsetMinutes", offset));
        } else if (body.containsKey("timestamp")) {
            String timestamp = (String) body.get("timestamp");
            try {
                LocalDateTime fixed = LocalDateTime.parse(timestamp, DateTimeFormatter.ISO_LOCAL_DATE_TIME);
                SystemClockService.setFixed(fixed);
                log.info("Clock fixed at {}", fixed);
                return ResponseEntity.ok(Map.of("timestamp", fixed.toString()));
            } catch (DateTimeParseException e) {
                return ResponseEntity.badRequest().body(Map.of("error", "Invalid timestamp format, use ISO_LOCAL_DATE_TIME"));
            }
        }
        return ResponseEntity.badRequest().body(Map.of("error", "Either offsetMinutes or timestamp is required"));
    }

    @DeleteMapping("/clock")
    public ResponseEntity<Map<String, Object>> resetClock() {
        SystemClockService.reset();
        log.info("Clock reset to system time");
        return ResponseEntity.ok(Map.of("reset", true));
    }
}
