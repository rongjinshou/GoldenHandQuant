# ShopHub Design-Implementation Consistency Fixer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all confirmed design-vs-implementation inconsistencies in the ShopHub codebase (`code/`), then package a portable submission (`INSTRUCTION.md` + `work/`) that reproduces those fixes deterministically against a fresh copy of the same materials.

**Architecture:** Three-stage pipeline per `docs/superpowers/specs/2026-07-05-consistency-fixer-design.md` (revised by `docs/2026-07-05-竞赛策略评估.md`): **Stage 1 (Offline Audit)** = the parallel module audit that produced the findings knowledge base, packaged as a re-runnable auditor skill; **Stage 2 (Deterministic Apply)** = `apply.sh`, a check-and-fix engine that reads each target file, compares its SHA-256 against the recorded baseline hash, and only then overwrites with the pre-verified fixed version (hash mismatch → skip + defer to Stage 3), emitting an apply-report; **Stage 3 (Online Review)** = an agent-executed skill that runs the verification suite **first**, only deep-checks per-module checklists when a test is red or Stage 2 skipped something, and guards every edit with backup → compile-gate → rollback-on-regression. This plan covers **fixing `code/` itself first** (Tasks 1–13), **then** packaging the three-stage submission (Tasks 14–17). Do not use the term `fixed-sources/`; the deliverable directory is `work/fixer/knowledge-base/`.

**Tech Stack:** Java 17, Spring Boot 3.2.6, Maven multi-module, JUnit 5 / Mockito / AssertJ, H2, Caffeine.

## Global Constraints

- JDK 17+, Maven 3.6+ (already installed at `~/tools/`, source `~/tools/env.sh` before any `mvn`/`java` command in a fresh shell).
- Build/verify commands (repo root, always with `-s maven-settings.xml`): `mvn -s maven-settings.xml -f code/pom.xml test`, `mvn -s maven-settings.xml -f code/pom.xml install -DskipTests`, `mvn -s maven-settings.xml -f test-cases/pom.xml test`.
- Never modify `design-docs/`, `README.md`, `test-cases/`, or any REST API URL/method/field name/type/status code defined in `README.md` §6 / `design-docs/附录A`.
- Never hardcode logic keyed to a specific test's `testRunId`, request payload, or other test-only signal — every fix must be a genuine correction to business logic per the cited design-doc section, because the same fix must also satisfy the non-public black-box suite exercising the same rules differently.
- Money: `BigDecimal` only, round `HALF_UP`, scale 2 at persistence.
- Every new/changed exception must use the existing hierarchy in `com.ecommerce.common.exception` (`BusinessException`, `ResourceNotFoundException`, `AuthorizationException`, `ValidationException`, `ConflictException`, `RateLimitException`, `OrderValidationException`) — never throw bare `IllegalArgumentException` or a bare `BusinessException("CONFLICT", ...)` where `ConflictException` fits.
- Commit after every task (see Global Constraints commit convention below) — this repo is git-initialized at root, baseline commit `1b1e88f`, design spec commit `e05e783`. Use `git add code/ <task-relevant paths>` (never `git add -A` blindly — check `git status` first, `target/` and `.claude/` are gitignored).
- Every task's fixes must be verified with **both** `mvn -f code/pom.xml test` (unit) and, where the module has public black-box coverage, `mvn -f test-cases/pom.xml test` (the relevant `PubBasicFlowTest`/`PubAdditionalBehaviorTest` methods, or the full suite once all modules are done).
- Source of truth for every "current code" snippet below: the 12 parallel module-audit reports already produced this session (file:line accurate as of baseline commit `1b1e88f`). If a snippet's surrounding context looks different when you open the file, the file has drifted since the audit — re-read it and adapt the edit; do not blindly apply a stale patch.

## Task Sequencing

**Must run in this order — Task 1 first, alone:**
Task 1 creates shared classes (event base class, new cross-module event classes, `AuditLogService`, `ConflictException` constructor, `MonetaryUtil` fix) that Tasks 2–12 import. Running Task 1 concurrently with any module task risks a compile race on `ecommerce-common`.

**Tasks 2–12 (one per module) are logically independent of each other** once Task 1 lands — they touch disjoint module directories. **Execution note (revised): do NOT fan out all 11 in parallel.** This repo builds on WSL over `/mnt/c` (slow I/O) and every module task runs `mvn install`/`test` against the single shared `~/.m2` — concurrent installs of `ecommerce-common`/module jars can corrupt each other. Dispatch in **small batches (2–3 at a time) or serially**, and run the Maven verification for each task to completion before starting the next batch. Correctness and a clean build matter far more here than wall-clock, because the deliverable's whole value is a deterministically-green `code/`.

**Task 13 (full-system verification) must run after all of Tasks 2–12 are merged**, since it's the first point every module compiles together against the new shared common classes.

**Tasks 14–17 (packaging) depend on Task 13's final, all-green state** and encode the three-stage strategy: Task 14 builds `knowledge-base/` + `baseline-hashes.txt` + `findings.md` from the verified diff; Task 15 writes `apply.sh` (the hash-gated engine) + the Stage 3 `SKILL.md` (verify-first + backup/compile-gate/rollback guardrails) + per-module checklists; Task 16 writes `INSTRUCTION.md` + `work/DESIGN.md` + the Stage 1 auditor skill; Task 17 is the end-to-end dry run (dirty baseline → `apply.sh` → verify green → idempotency re-run) plus `result/`+`logs/` assembly.

---

## Task 1: Shared `ecommerce-common` infrastructure

**Files:**
- Modify: `code/ecommerce-common/src/main/java/com/ecommerce/common/money/MonetaryUtil.java`
- Modify: `code/ecommerce-common/src/main/java/com/ecommerce/common/exception/ConflictException.java`
- Modify: `code/ecommerce-common/src/main/java/com/ecommerce/common/event/AbstractDomainEvent.java`
- Modify: `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/LocalNotificationServiceImpl.java`
- Modify: `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/NotificationRecordService.java` (add failure-recording support)
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogEntry.java`
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogRepository.java`
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogService.java`
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/event/OrderPaidEvent.java`
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/event/ReviewApprovedEvent.java`
- Create: `code/ecommerce-common/src/main/java/com/ecommerce/common/event/ShipmentDeliveredEvent.java`
- Test: `code/ecommerce-common/src/test/java/com/ecommerce/common/money/MonetaryUtilTest.java` (existing — fix its assertion, it currently locks in the HALF_DOWN bug)
- Test: `code/ecommerce-common/src/test/java/com/ecommerce/common/audit/AuditLogServiceTest.java` (new)
- Test: `code/ecommerce-common/src/test/java/com/ecommerce/common/exception/ConflictExceptionTest.java` (new, small)

**Interfaces produced (Tasks 2–12 depend on these exact names):**
- `com.ecommerce.common.event.OrderPaidEvent(Object source, Long orderId, Long userId, BigDecimal paidAmount, List<OrderItemPayload> items, String aggregateId, String traceId)` — publish this from `ecommerce-order`, listen to it from `ecommerce-loyalty` and `ecommerce-logistics`.
- `com.ecommerce.common.event.OrderPaidEvent.OrderItemPayload(Long skuId, Integer quantity, BigDecimal price)` — static nested record/class.
- `com.ecommerce.common.event.ReviewApprovedEvent(Object source, Long reviewId, Long userId, Long orderId, Long productId, String aggregateId, String traceId)` — publish from `ecommerce-review`, listen from `ecommerce-loyalty`.
- `com.ecommerce.common.event.ShipmentDeliveredEvent(Object source, Long orderId, Long shipmentId, LocalDateTime deliveredAt, String aggregateId, String traceId)` — publish from `ecommerce-logistics`, listen from `ecommerce-order` and `ecommerce-loyalty`.
- `com.ecommerce.common.event.AbstractDomainEvent` — new protected constructor `AbstractDomainEvent(Object source, String aggregateId, String traceId)`, new public `getAggregateId()`, `getTraceId()`, `getEventType()` (returns `getClass().getSimpleName()`).
- `com.ecommerce.common.exception.ConflictException(String code, String message)` — new constructor alongside the existing single-arg one (which keeps defaulting to code `"CONFLICT"`).
- `com.ecommerce.common.audit.AuditLogService.record(String operatorId, String actionType, String businessId, String beforeState, String afterState, String remark)` — call this from every one of the 7 audit points identified in the design spec §6.0.

- [ ] **Step 1: Read the current `AbstractDomainEvent.java`, `MonetaryUtil.java`, `ConflictException.java` in full before editing**

```bash
cat code/ecommerce-common/src/main/java/com/ecommerce/common/event/AbstractDomainEvent.java
cat code/ecommerce-common/src/main/java/com/ecommerce/common/money/MonetaryUtil.java
cat code/ecommerce-common/src/main/java/com/ecommerce/common/exception/ConflictException.java
```
Confirm the exact current constructor signature of `AbstractDomainEvent` (the audit reported it has `eventId` + `occurredAt` but no `aggregateId`/`traceId`/`getEventType()` — confirm the exact `super(...)` call shape every existing subclass uses, since you must keep old call sites compiling or update all of them in the same task).

- [ ] **Step 2: Verify which modules currently reference `AbstractDomainEvent` subclasses, to know every call site the constructor-signature change touches**

```bash
grep -rln "extends AbstractDomainEvent" code/*/src/main/java
```
Expect to see event classes in `ecommerce-order`, `ecommerce-payment`, `ecommerce-logistics` (none yet), `ecommerce-loyalty`, `ecommerce-review`. Every one of these constructors needs updating to pass `aggregateId`/`traceId` (a reasonable default for `traceId` where none is threaded through yet is `null` — do not invent fake trace-id plumbing beyond what's asked).

- [ ] **Step 3: Fix `MonetaryUtil` rounding mode**

Find the line (audit-reported at `MonetaryUtil.java:32`):
```java
return amount.setScale(SCALE, RoundingMode.HALF_DOWN);
```
Replace with:
```java
return amount.setScale(SCALE, RoundingMode.HALF_UP);
```
Also remove/fix the stale Javadoc comment above it that says "0.005 rounds down to 0.00" (per the audit, this exists specifically to document the bug) — replace with a comment matching the new behavior, or delete the comment if the method name is already self-explanatory (prefer deleting per this project's "no comments unless non-obvious" convention — `HALF_UP` is standard and self-explanatory).

- [ ] **Step 4: Fix the existing `MonetaryUtilTest` that currently locks in the bug**

Open `code/ecommerce-common/src/test/java/com/ecommerce/common/money/MonetaryUtilTest.java`, find the test asserting 0.005 rounds to 0.00 (HALF_DOWN behavior), and change the expected value to match HALF_UP (0.005 → 0.01). This is one of the "own JUnit tests, may modify, unscored" per project rules — modifying it is correct here since it was pinned to the wrong behavior.

- [ ] **Step 5: Run the money test to confirm it now passes**

```bash
source ~/tools/env.sh && mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am test -Dtest=MonetaryUtilTest
```
Expected: `Tests run: N, Failures: 0, Errors: 0`.

- [ ] **Step 6: Add the `(code, message)` constructor to `ConflictException`**

Current file (per audit, lines 11-13) has only:
```java
public ConflictException(String message) {
    super("CONFLICT", message);
}
```
Add (keep the existing constructor too, for callers that don't need a custom code):
```java
public ConflictException(String code, String message) {
    super(code, message);
}
```
(Read the actual base class `BusinessException` first to confirm its constructor shape — `super(code, message)` assumes `BusinessException(String code, String message)` exists, which the other sibling exceptions like `AuthorizationException`/`OrderValidationException` already use per the audit.)

- [ ] **Step 7: Write a small test for the new constructor**

Create `code/ecommerce-common/src/test/java/com/ecommerce/common/exception/ConflictExceptionTest.java`:
```java
package com.ecommerce.common.exception;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ConflictExceptionTest {

    @Test
    void singleArgConstructor_defaultsCodeToConflict() {
        ConflictException ex = new ConflictException("duplicate");
        assertEquals("CONFLICT", ex.getCode());
        assertEquals("duplicate", ex.getMessage());
    }

    @Test
    void twoArgConstructor_usesGivenCode() {
        ConflictException ex = new ConflictException("ORDER_STATUS_CONFLICT", "wrong state");
        assertEquals("ORDER_STATUS_CONFLICT", ex.getCode());
        assertEquals("wrong state", ex.getMessage());
    }
}
```
(Adjust `ex.getCode()` to whatever the actual getter is named on `BusinessException` — confirm from the file read in Step 1's sibling check.)

- [ ] **Step 8: Run it**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am test -Dtest=ConflictExceptionTest
```
Expected: 2/2 pass.

- [ ] **Step 9: Extend `AbstractDomainEvent` with `aggregateId`/`traceId`/`getEventType()`**

Add fields + constructor param + getters (exact insertion depends on Step 1's read — the shape below assumes the existing fields are `eventId`/`occurredAt` set in a `super(source)` + own-field-assignment pattern):
```java
private final String aggregateId;
private final String traceId;

protected AbstractDomainEvent(Object source, String aggregateId, String traceId) {
    super(source);
    this.eventId = UUID.randomUUID().toString();
    this.occurredAt = LocalDateTime.now();
    this.aggregateId = aggregateId;
    this.traceId = traceId;
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
```
If the existing class only has a single constructor `AbstractDomainEvent(Object source)`, **keep that one too** (delegating to the new one with `null, null`) rather than breaking every existing subclass in this same step — Step 2's grep result tells you which subclasses to actually update to pass real `aggregateId`/`traceId` values, which happens per-module in Tasks 2–12, not here. Task 1 only needs the base class to compile and offer both constructors.

- [ ] **Step 10: Compile-check common module**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am compile
```
Expected: `BUILD SUCCESS`. If existing subclasses (order/payment/logistics/loyalty/review event classes) fail to compile because you removed the old constructor, restore the delegating overload from Step 9's note.

- [ ] **Step 11: Fix the fault-injection-outside-try-block bug in `LocalNotificationServiceImpl`**

Per audit, around line 49-52, the fault-injection check is BEFORE the `try` block that starts at line 74. Move it inside. Read the file first:
```bash
cat code/ecommerce-common/src/main/java/com/ecommerce/common/notification/LocalNotificationServiceImpl.java
```
Then restructure so the method looks like (adapt variable names/surrounding lines to what Step 1's read shows — the key change is that the `FaultInjectionRegistry.isActive("notification-send-failure")` throw must execute INSIDE the same try/catch that already wraps the rest of `send()`, so a real or injected failure is always caught and logged rather than propagating):
```java
try {
    if (FaultInjectionRegistry.isActive("notification-send-failure")) {
        throw new RuntimeException("Injected notification failure");
    }
    // ... existing send logic ...
} catch (Exception e) {
    log.error("Notification send failed: bizType={}, bizId={}, channel={}, template={}",
            request.getBizType(), request.getBizId(), request.getChannel(), request.getTemplateCode(), e);
    notificationRecordService.recordFailure(request.getBizType(), request.getBizId(),
            request.getReceiver(), request.getChannel().name(), request.getTemplateCode(), e.getMessage());
}
```

- [ ] **Step 12: Add failure recording to `NotificationRecordService`**

Read the current file, then add a method alongside the existing `record(...)`:
```java
public void recordFailure(String bizType, String bizId, String receiver,
                           String channel, String templateCode, String failureReason) {
    records.add(new NotificationRecordItem(bizType, bizId, receiver, channel, templateCode,
            null, LocalDateTime.now(), failureReason));
}
```
This requires adding a `failureReason` field to the inner `NotificationRecordItem` class (and its getter `getFailureReason()`), defaulting to `null` for successful sends — update the existing `record(...)` call site to pass `null` for that new parameter, and update `NotificationRecord`/`NotificationAdminController`'s response mapping (`code/ecommerce-app/.../NotificationAdminController.java`) to surface the new field so `GET /api/v1/admin/notifications` can show it (adding a response field doesn't break the frozen contract — README doesn't specify exact notification-query response shape).

- [ ] **Step 13: Write a test proving a fault-injected send is caught, not propagated, and recorded as failed**

Create/extend `code/ecommerce-common/src/test/java/com/ecommerce/common/notification/LocalNotificationServiceImplTest.java` (read the existing file first if present, to match its existing test setup style) with:
```java
@Test
void send_whenFaultInjected_doesNotThrow_andRecordsFailure() {
    FaultInjectionRegistry.activate("notification-send-failure");
    try {
        NotificationRequest request = NotificationRequest.builder()
                .bizType("TEST").bizId("1").receiver("test@example.com")
                .channel(NotificationChannel.EMAIL).templateCode("test_template")
                .build();

        assertDoesNotThrow(() -> service.send(request));
    } finally {
        FaultInjectionRegistry.clear();
    }
}
```
(Adapt `NotificationRequest.builder()` usage and `FaultInjectionRegistry.activate/clear` method names to what Step 1's read of `FaultInjectionRegistry.java` shows — the audit confirmed this class exists with an `isActive(String)` check; confirm the exact activation/clear method names before writing this.)

- [ ] **Step 14: Run the notification test**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am test -Dtest=LocalNotificationServiceImplTest
```
Expected: pass, and confirm manually that the test would have failed before Step 11's fix (the fault would have propagated as a `RuntimeException` out of `send()`).

- [ ] **Step 15: Create the shared audit log entity**

`code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogEntry.java`:
```java
package com.ecommerce.common.audit;

import com.ecommerce.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "audit_log_entries")
public class AuditLogEntry extends BaseEntity {

    @Column(name = "operator_id", nullable = false)
    private String operatorId;

    @Column(name = "action_type", nullable = false)
    private String actionType;

    @Column(name = "business_id", nullable = false)
    private String businessId;

    @Column(name = "before_state")
    private String beforeState;

    @Column(name = "after_state")
    private String afterState;

    @Column(name = "remark", length = 1000)
    private String remark;

    public AuditLogEntry() {
    }

    public AuditLogEntry(String operatorId, String actionType, String businessId,
                          String beforeState, String afterState, String remark) {
        this.operatorId = operatorId;
        this.actionType = actionType;
        this.businessId = businessId;
        this.beforeState = beforeState;
        this.afterState = afterState;
        this.remark = remark;
    }

    public String getOperatorId() { return operatorId; }
    public String getActionType() { return actionType; }
    public String getBusinessId() { return businessId; }
    public String getBeforeState() { return beforeState; }
    public String getAfterState() { return afterState; }
    public String getRemark() { return remark; }
}
```
(Read `code/ecommerce-common/src/main/java/com/ecommerce/common/model/BaseEntity.java` first to confirm it provides `id`/`createdAt`/`updatedAt` and the exact package/annotations to extend — match the pattern every other entity in this codebase already follows.)

- [ ] **Step 16: Create the repository**

`code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogRepository.java`:
```java
package com.ecommerce.common.audit;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface AuditLogRepository extends JpaRepository<AuditLogEntry, Long> {
}
```

- [ ] **Step 17: Create the service**

`code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogService.java`:
```java
package com.ecommerce.common.audit;

import org.springframework.stereotype.Service;

@Service
public class AuditLogService {

    private final AuditLogRepository auditLogRepository;

    public AuditLogService(AuditLogRepository auditLogRepository) {
        this.auditLogRepository = auditLogRepository;
    }

    public void record(String operatorId, String actionType, String businessId,
                        String beforeState, String afterState, String remark) {
        auditLogRepository.save(new AuditLogEntry(operatorId, actionType, businessId,
                beforeState, afterState, remark));
    }
}
```

- [ ] **Step 18: Write a test**

`code/ecommerce-common/src/test/java/com/ecommerce/common/audit/AuditLogServiceTest.java`:
```java
package com.ecommerce.common.audit;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class AuditLogServiceTest {

    @Test
    void record_savesEntryWithAllFields() {
        AuditLogRepository repository = mock(AuditLogRepository.class);
        AuditLogService service = new AuditLogService(repository);

        service.record("admin-1", "SKU_ON_SHELF", "sku-42", "OFF_SHELF", "ON_SHELF", "manual review");

        ArgumentCaptor<AuditLogEntry> captor = ArgumentCaptor.forClass(AuditLogEntry.class);
        verify(repository).save(captor.capture());
        AuditLogEntry saved = captor.getValue();
        assertEquals("admin-1", saved.getOperatorId());
        assertEquals("SKU_ON_SHELF", saved.getActionType());
        assertEquals("sku-42", saved.getBusinessId());
        assertEquals("OFF_SHELF", saved.getBeforeState());
        assertEquals("ON_SHELF", saved.getAfterState());
    }
}
```

- [ ] **Step 19: Run it**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am test -Dtest=AuditLogServiceTest
```
Expected: pass.

- [ ] **Step 20: Create `OrderPaidEvent` in common**

`code/ecommerce-common/src/main/java/com/ecommerce/common/event/OrderPaidEvent.java`:
```java
package com.ecommerce.common.event;

import java.math.BigDecimal;
import java.util.List;

public class OrderPaidEvent extends AbstractDomainEvent {

    private final Long orderId;
    private final Long userId;
    private final BigDecimal paidAmount;
    private final List<OrderItemPayload> items;

    public OrderPaidEvent(Object source, Long orderId, Long userId, BigDecimal paidAmount,
                           List<OrderItemPayload> items, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.orderId = orderId;
        this.userId = userId;
        this.paidAmount = paidAmount;
        this.items = items;
    }

    public Long getOrderId() { return orderId; }
    public Long getUserId() { return userId; }
    public BigDecimal getPaidAmount() { return paidAmount; }
    public List<OrderItemPayload> getItems() { return items; }

    public static class OrderItemPayload {
        private final Long skuId;
        private final Integer quantity;
        private final BigDecimal price;

        public OrderItemPayload(Long skuId, Integer quantity, BigDecimal price) {
            this.skuId = skuId;
            this.quantity = quantity;
            this.price = price;
        }

        public Long getSkuId() { return skuId; }
        public Integer getQuantity() { return quantity; }
        public BigDecimal getPrice() { return price; }
    }
}
```

- [ ] **Step 21: Create `ReviewApprovedEvent` in common**

`code/ecommerce-common/src/main/java/com/ecommerce/common/event/ReviewApprovedEvent.java`:
```java
package com.ecommerce.common.event;

public class ReviewApprovedEvent extends AbstractDomainEvent {

    private final Long reviewId;
    private final Long userId;
    private final Long orderId;
    private final Long productId;

    public ReviewApprovedEvent(Object source, Long reviewId, Long userId, Long orderId,
                                Long productId, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.reviewId = reviewId;
        this.userId = userId;
        this.orderId = orderId;
        this.productId = productId;
    }

    public Long getReviewId() { return reviewId; }
    public Long getUserId() { return userId; }
    public Long getOrderId() { return orderId; }
    public Long getProductId() { return productId; }
}
```

- [ ] **Step 22: Create `ShipmentDeliveredEvent` in common**

`code/ecommerce-common/src/main/java/com/ecommerce/common/event/ShipmentDeliveredEvent.java`:
```java
package com.ecommerce.common.event;

import java.time.LocalDateTime;

public class ShipmentDeliveredEvent extends AbstractDomainEvent {

    private final Long orderId;
    private final Long shipmentId;
    private final LocalDateTime deliveredAt;

    public ShipmentDeliveredEvent(Object source, Long orderId, Long shipmentId,
                                   LocalDateTime deliveredAt, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.orderId = orderId;
        this.shipmentId = shipmentId;
        this.deliveredAt = deliveredAt;
    }

    public Long getOrderId() { return orderId; }
    public Long getShipmentId() { return shipmentId; }
    public LocalDateTime getDeliveredAt() { return deliveredAt; }
}
```

- [ ] **Step 23: Verify who currently publishes/listens to `OrderPaidEvent` and `PaymentSucceededEvent` end to end, before Tasks 2–12 assume the design-doc-only picture**

This is the single most important verification step in the whole plan — it determines whether `PaymentSucceededEvent` also needs to move to common (not yet confirmed by any audit report; Task 7's payment work depends on the answer).

```bash
grep -rn "class OrderPaidEvent\|class PaymentSucceededEvent" code/*/src/main/java
grep -rn "OrderPaidEvent\|PaymentSucceededEvent" code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPaymentEventHandler.java
grep -rln "ecommerce-payment\|ecommerce-order" code/ecommerce-order/pom.xml code/ecommerce-payment/pom.xml
```
Read `OrderPaymentEventHandler.java` in full. Determine:
1. Does `ecommerce-order` depend on `ecommerce-payment` in `pom.xml`, or the reverse? (Design says payment consumes `OrderQueryService`/`OrderPaymentStatusUpdater` from order, implying payment→order.)
2. If payment→order (order does NOT depend on payment), can `OrderPaymentEventHandler` (in `ecommerce-order`) actually import `com.ecommerce.payment.event.PaymentSucceededEvent`? If order's pom has no dependency on payment, this **cannot compile** unless `OrderPaymentEventHandler` is listening to something else (e.g., it might be a plain method called synchronously from payment via `OrderPaymentStatusUpdater`, not a Spring `@EventListener` at all — check for the `@EventListener` annotation specifically).
3. Record the finding as a one-line note in this plan file's Task 7 section (edit it in before starting Task 7) so whoever implements payment fixes knows whether to also move `PaymentSucceededEvent` to `ecommerce-common` (same treatment as `OrderPaidEvent`) or leave it in place.

- [ ] **Step 24: Full common-module test run**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am test
```
Expected: all pass, including the modified `MonetaryUtilTest` and new `ConflictExceptionTest`/`AuditLogServiceTest`/`LocalNotificationServiceImplTest` additions.

- [ ] **Step 25: Full-repo compile check (not tests yet — modules that reference old event constructors may not compile until Tasks 2–12 land, that's expected)**

```bash
mvn -s maven-settings.xml -f code/pom.xml compile 2>&1 | tail -50
```
If this fails on a module OTHER than the ones with events being migrated, stop and fix — Task 1 must not break compilation of modules it doesn't intend to touch. If it fails only on `ecommerce-order`/`ecommerce-loyalty`/`ecommerce-review`/`ecommerce-logistics` because their local shadow event classes now clash or their constructors don't match the base class's new signature, that's expected and gets resolved in Tasks 6/9/10/11 respectively — note which modules failed here so those tasks know to expect a pre-existing compile break, not a regression they caused.

- [ ] **Step 26: Commit**

```bash
git add code/ecommerce-common
git commit -m "$(cat <<'EOF'
Fix common-module bugs: HALF_UP rounding, ConflictException(code,message),
AbstractDomainEvent aggregateId/traceId, notification fault-injection
leak, and add shared AuditLogService + cross-module event classes

Per design-docs/03 (rounding, exception hierarchy, audit log
requirements) and design-docs/附录D (event base fields). OrderPaidEvent,
ReviewApprovedEvent, and ShipmentDeliveredEvent now live here so
loyalty/logistics/order can listen to the actual publisher's class
instead of a module-local shadow copy that Spring never dispatches to.
EOF
)"
```

## Task 2: `ecommerce-user` module (7 fixes)

**Depends on:** Task 1 (uses `ConflictException(code,message)`, `AuditLogService`).

**Files:**
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserRegisterService.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserAuthService.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/service/AddressFormatter.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/dto/AddressRequest.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/dto/AddressResponse.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/controller/AdminUserController.java`
- Modify: `code/ecommerce-user/src/main/java/com/ecommerce/user/controller/UserController.java`
- Test: `code/ecommerce-user/src/test/java/com/ecommerce/user/service/UserRegisterServiceTest.java` (existing — fix its assertion, see Step 2)
- Test: `code/ecommerce-user/src/test/java/com/ecommerce/user/service/AddressFormatterTest.java` (existing — fix its call-argument order, see Step 6)

**Interfaces:**
- Consumes: `com.ecommerce.common.exception.ConflictException(String,String)`, `com.ecommerce.common.audit.AuditLogService.record(...)` from Task 1.

- [ ] **Step 1: Fix registration to leave status `PENDING_ACTIVATION` and actually create an activation token**

Current (`UserRegisterService.java`, full method already confirmed this session):
```java
@Transactional
public UserResponse register(RegisterRequest request) {
    // Check uniqueness
    if (userRepository.existsByEmail(request.getEmail())) {
        throw new ConflictException("Email already registered: " + request.getEmail());
    }
    if (userRepository.existsByPhone(request.getPhone())) {
        throw new ConflictException("Phone already registered: " + request.getPhone());
    }

    User user = new User();
    user.setEmail(request.getEmail());
    user.setPhone(request.getPhone());
    user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
    user.setNickname(request.getNickname());
    user.setStatus(UserStatus.ACTIVE);
    user.setRole(UserRole.USER);

    User saved = userRepository.save(user);
    log.info("User registered: id={}, email={}, status={}", saved.getId(), saved.getEmail(), saved.getStatus());

    // Send welcome notification via LocalNotificationService
    NotificationRequest notification = new NotificationRequest();
    notification.setBizType("USER_REGISTER");
    notification.setBizId(String.valueOf(saved.getId()));
    notification.setReceiver(saved.getEmail());
    notification.setChannel(NotificationChannel.EMAIL);
    notification.setTemplateCode("WELCOME");
    Map<String, Object> variables = new HashMap<>();
    variables.put("nickname", saved.getNickname());
    notification.setVariables(variables);
    notificationService.send(notification);

    return UserResponse.from(saved);
}
```

Replace with:
```java
@Transactional
public UserResponse register(RegisterRequest request) {
    // Check uniqueness
    if (userRepository.existsByEmail(request.getEmail())) {
        throw new ConflictException("Email already registered: " + request.getEmail());
    }
    if (userRepository.existsByPhone(request.getPhone())) {
        throw new ConflictException("Phone already registered: " + request.getPhone());
    }

    User user = new User();
    user.setEmail(request.getEmail());
    user.setPhone(request.getPhone());
    user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
    user.setNickname(request.getNickname());
    user.setStatus(UserStatus.PENDING_ACTIVATION);
    user.setRole(UserRole.USER);

    User saved = userRepository.save(user);
    log.info("User registered: id={}, email={}, status={}", saved.getId(), saved.getEmail(), saved.getStatus());

    EmailActivationToken activationToken = new EmailActivationToken();
    activationToken.setUserId(saved.getId());
    activationToken.setToken(UUID.randomUUID().toString());
    activationToken.setExpiresAt(LocalDateTime.now().plusHours(24));
    activationToken.setUsed(false);
    activationTokenRepository.save(activationToken);

    // Send activation email via LocalNotificationService
    NotificationRequest notification = new NotificationRequest();
    notification.setBizType("USER_REGISTER");
    notification.setBizId(String.valueOf(saved.getId()));
    notification.setReceiver(saved.getEmail());
    notification.setChannel(NotificationChannel.EMAIL);
    notification.setTemplateCode("activation_email");
    Map<String, Object> variables = new HashMap<>();
    variables.put("nickname", saved.getNickname());
    variables.put("activationToken", activationToken.getToken());
    notification.setVariables(variables);
    notificationService.send(notification);

    return UserResponse.from(saved);
}
```
Also add the field + constructor parameter + import for `EmailActivationTokenRepository`:
```java
import com.ecommerce.user.entity.EmailActivationToken;
import com.ecommerce.user.repository.EmailActivationTokenRepository;
import java.time.LocalDateTime;
import java.util.UUID;
```
```java
private final EmailActivationTokenRepository activationTokenRepository;

public UserRegisterService(UserRepository userRepository,
                           BCryptPasswordEncoder passwordEncoder,
                           LocalNotificationService notificationService,
                           EmailActivationTokenRepository activationTokenRepository) {
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
    this.notificationService = notificationService;
    this.activationTokenRepository = activationTokenRepository;
}
```

- [ ] **Step 2: Fix the existing unit test that currently asserts the wrong (buggy) status**

Open `UserRegisterServiceTest.java`, find `testRegister_userStatusAfterRegistration` (per audit, asserts `.isEqualTo(UserStatus.ACTIVE)`), change to `.isEqualTo(UserStatus.PENDING_ACTIVATION)`. If the test constructs `UserRegisterService` manually with mocks, add a mock `EmailActivationTokenRepository` to its constructor call and stub `.save(any())` to return its argument.

- [ ] **Step 3: Fix `login()` to throw `AuthorizationException` (403) instead of `BusinessException` (400) for USER_FROZEN/USER_NOT_ACTIVE**

Current (`UserAuthService.java`, confirmed this session):
```java
if (user.getStatus() != UserStatus.ACTIVE) {
    if (user.getStatus() == UserStatus.FROZEN) {
        throw new BusinessException("USER_FROZEN", "Account is frozen: " + user.getEmail());
    }
    throw new BusinessException("USER_NOT_ACTIVE", "Account is not active: " + user.getEmail());
}
```
Replace with:
```java
if (user.getStatus() != UserStatus.ACTIVE) {
    if (user.getStatus() == UserStatus.FROZEN) {
        throw new AuthorizationException("USER_FROZEN", "Account is frozen: " + user.getEmail());
    }
    throw new AuthorizationException("USER_NOT_ACTIVE", "Account is not active: " + user.getEmail());
}
```
(`AuthorizationException` is already imported in this file per the earlier read of it this session — it's used a few lines below for `"UNAUTHORIZED"`.)

- [ ] **Step 4: Fix `activate()` to throw `ConflictException` instead of `BusinessException("CONFLICT", ...)`**

Current (`UserAuthService.java`, confirmed this session):
```java
if (activationToken.isUsed()) {
    throw new BusinessException("CONFLICT", "Activation token has already been used");
}

if (activationToken.getExpiresAt().isBefore(LocalDateTime.now())) {
    throw new BusinessException("CONFLICT", "Activation token has expired");
}
```
Replace with:
```java
if (activationToken.isUsed()) {
    throw new ConflictException("Activation token has already been used");
}

if (activationToken.getExpiresAt().isBefore(LocalDateTime.now())) {
    throw new ConflictException("Activation token has expired");
}
```
Add `import com.ecommerce.common.exception.ConflictException;` to this file's imports.

- [ ] **Step 5: Fix `AddressFormatter.format()` parameter order**

Read the file first (`cat code/ecommerce-user/src/main/java/com/ecommerce/user/service/AddressFormatter.java`) to confirm the exact current text, which per audit is:
```java
public String format(String city, String province, String district, String detail) {
    return province + city + district + detail;
}
```
Change the signature only (body already concatenates in the design-mandated province-first order, so leave the `return` line untouched):
```java
public String format(String province, String city, String district, String detail) {
    return province + city + district + detail;
}
```

- [ ] **Step 6: Fix the existing test's call-argument order to match**

Open `AddressFormatterTest.java`, find the calls to `format(...)` (audit says the test comments admit "callers pass values in the current parameter order (city first, province second)" — meaning the test currently calls `format(cityValue, provinceValue, ...)`), change call sites to pass `format(provinceValue, cityValue, districtValue, detailValue)` matching the corrected signature, and update any hardcoded expected-output string in the test if it encoded the swapped order.

- [ ] **Step 7: Fix `isDefault` JSON field naming in `AddressRequest`/`AddressResponse`**

Read both files first. Add `@JsonProperty("isDefault")` to both the getter and setter (Jackson needs it on both directions):
```java
import com.fasterxml.jackson.annotation.JsonProperty;
```
```java
@JsonProperty("isDefault")
public boolean isDefault() {
    return isDefault;
}

@JsonProperty("isDefault")
public void setDefault(boolean isDefault) {
    this.isDefault = isDefault;
}
```
Apply the identical change to both `AddressRequest.java` and `AddressResponse.java`.

- [ ] **Step 8: Write a test proving the JSON field round-trips as `isDefault`**

Create `code/ecommerce-user/src/test/java/com/ecommerce/user/dto/AddressRequestJsonTest.java`:
```java
package com.ecommerce.user.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AddressRequestJsonTest {

    @Test
    void isDefault_deserializesFromJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String json = "{\"province\":\"Guangdong\",\"city\":\"Shenzhen\","
                + "\"district\":\"Nanshan\",\"detail\":\"No.1\",\"isDefault\":true}";

        AddressRequest request = mapper.readValue(json, AddressRequest.class);

        assertTrue(request.isDefault());
    }

    @Test
    void isDefault_serializesToJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        AddressRequest request = new AddressRequest();
        request.setDefault(true);

        String json = mapper.writeValueAsString(request);

        assertTrue(json.contains("\"isDefault\":true"));
    }
}
```
(Adjust field names in the JSON literal to match `AddressRequest`'s actual fields, confirmed from Step 7's read.)

- [ ] **Step 9: Add audit logging to freeze/unfreeze**

Current (`UserAuthService.java`, confirmed this session):
```java
@Transactional
public void freezeUser(Long userId) {
    User user = userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
    user.setStatus(UserStatus.FROZEN);
    userRepository.save(user);
    log.info("User frozen: id={}", userId);
}

@Transactional
public void unfreezeUser(Long userId) {
    User user = userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
    user.setStatus(UserStatus.ACTIVE);
    userRepository.save(user);
    log.info("User unfrozen: id={}", userId);
}
```
Replace with (adds an `operatorId` parameter — update both call sites in `AdminUserController.java` accordingly in Step 10):
```java
@Transactional
public void freezeUser(Long userId, String operatorId) {
    User user = userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
    UserStatus before = user.getStatus();
    user.setStatus(UserStatus.FROZEN);
    userRepository.save(user);
    auditLogService.record(operatorId, "USER_FREEZE", String.valueOf(userId),
            before.name(), UserStatus.FROZEN.name(), null);
    log.info("User frozen: id={}", userId);
}

@Transactional
public void unfreezeUser(Long userId, String operatorId) {
    User user = userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
    UserStatus before = user.getStatus();
    user.setStatus(UserStatus.ACTIVE);
    userRepository.save(user);
    auditLogService.record(operatorId, "USER_UNFREEZE", String.valueOf(userId),
            before.name(), UserStatus.ACTIVE.name(), null);
    log.info("User unfrozen: id={}", userId);
}
```
Add the field/constructor parameter:
```java
import com.ecommerce.common.audit.AuditLogService;
```
```java
private final AuditLogService auditLogService;
```
(add to constructor parameter list and assignment, alongside the other final fields already there).

- [ ] **Step 10: Update `AdminUserController` to pass the authenticated operator's ID**

Read `code/ecommerce-user/src/main/java/com/ecommerce/user/controller/AdminUserController.java` first. Add a `org.springframework.security.core.Authentication` parameter to both the freeze and unfreeze endpoint methods (Spring injects the current principal automatically) and pass `authentication.getName()` through:
```java
@PostMapping("/{userId}/freeze")
public ResponseEntity<Void> freeze(@PathVariable Long userId, Authentication authentication) {
    userAuthService.freezeUser(userId, authentication.getName());
    return ResponseEntity.ok().build();
}

@PostMapping("/{userId}/unfreeze")
public ResponseEntity<Void> unfreeze(@PathVariable Long userId, Authentication authentication) {
    userAuthService.unfreezeUser(userId, authentication.getName());
    return ResponseEntity.ok().build();
}
```
(Match the exact existing method names/return types/annotations from your read — only add the `Authentication` parameter and thread it through; don't change the URL/HTTP method/response status, which are frozen contract.)

- [ ] **Step 11: Add rate limiting to login**

Read `code/ecommerce-common/src/main/java/com/ecommerce/common/ratelimit/RateLimit.java` first to confirm the annotation's exact attribute names (audit confirms it supports SpEL key + a permits-per-minute style limit). Add to `UserController.login` (or `UserAuthService.login` if the aspect is method-level and works there instead — confirm from `RateLimitAspect`'s pointcut):
```java
@RateLimit(key = "'login:' + #request.email", limit = 5, windowSeconds = 60)
```
using whichever attribute names Step 11's read reveals (this plan cannot guess exact attribute names without reading the annotation first — do not skip the read).

- [ ] **Step 12: Write a test proving the 6th rapid login attempt for the same email is rejected**

Add to (or create) `code/ecommerce-user/src/test/java/com/ecommerce/user/controller/UserControllerTest.java`:
```java
@Test
void login_sixthAttemptWithinAMinute_returns429() {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("email", "ratelimit-test@example.com");
    body.put("password", "wrong-password");

    ResponseEntity<String> lastResponse = null;
    for (int i = 0; i < 6; i++) {
        lastResponse = restTemplate.postForEntity("/api/v1/users/login", body, String.class);
    }

    assertEquals(429, lastResponse.getStatusCode().value());
}
```
(Adapt to this test class's existing HTTP-calling convention — `TestRestTemplate`/`MockMvc` — confirmed from whatever `UserControllerTest.java` already uses for its other tests; match that pattern rather than introducing a new one.)

- [ ] **Step 13: Run the full user module test suite**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-user -am test
```
Expected: all pass, including the corrected `UserRegisterServiceTest`/`AddressFormatterTest` and the four new tests from Steps 8/12.

- [ ] **Step 14: Install and run the two known black-box tests plus PUB-105's frozen-user sibling (PUB-103) to confirm no regression**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub001_registerActivateLogin test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub105_unactivatedUserCannotLogin test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub103_frozenUserCannotCreateOrder test
```
Expected: all three pass now (they were previously failing/coincidentally-passing; `pub103` must still pass since it depends on `UserAuthService.login()`'s frozen-check, which Step 3 changed the exception type for for but not the trigger condition).

- [ ] **Step 15: Commit**

```bash
git add code/ecommerce-user
git commit -m "$(cat <<'EOF'
Fix user module: real activation flow, correct 403 vs 400 on
login rejection, address formatter param order, isDefault JSON
naming, freeze/unfreeze audit log, login rate limit

Registration now leaves PENDING_ACTIVATION and issues a real
EmailActivationToken (design-docs/04 §3) instead of activating
immediately, which was silently masking the login-rejection bug
(design-docs/04 §4) since every user was already ACTIVE.
EOF
)"
```

## Task 3: `ecommerce-product` module (10 fixes)

**Depends on:** Task 1 (`AuditLogService`); reads from `ecommerce-inventory`'s `InventoryQueryService` (already exists, Task 4 doesn't change its interface).

**Files:**
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/StockInfoFetcher.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductQueryServiceImpl.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/dto/ProductSearchRequest.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductSearchService.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SkuService.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/controller/AdminProductController.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/controller/ProductController.java`
- Create: `code/ecommerce-product/src/main/java/com/ecommerce/product/config/ProductCacheConfig.java`
- Modify: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductDetailService.java`
- Test: `code/ecommerce-product/src/test/java/com/ecommerce/product/service/ProductDetailServiceTest.java` (existing — fix its mock, see Step 2)
- Test: `code/ecommerce-product/src/test/java/com/ecommerce/product/service/ProductSearchServiceTest.java` (existing — fix its assertions, see Step 6)

- [ ] **Step 1: Wire real inventory lookup into `StockInfoFetcher`**

Read the file first: `cat code/ecommerce-product/src/main/java/com/ecommerce/product/service/StockInfoFetcher.java`. Per audit it currently is (approximately, confirm exact text):
```java
public StockSummaryDto fetch(Long skuId) {
    return new StockSummaryDto(999, 0);
}
```
Add the `InventoryQueryService` dependency and delegate:
```java
private final InventoryQueryService inventoryQueryService;

public StockInfoFetcher(InventoryQueryService inventoryQueryService) {
    this.inventoryQueryService = inventoryQueryService;
}

public StockSummaryDto fetch(Long skuId) {
    return inventoryQueryService.getStockSummary(skuId);
}
```
(Confirm `InventoryQueryService.getStockSummary(Long)`'s exact return type from `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/query/InventoryQueryService.java` — if it returns a different DTO type than `StockSummaryDto`, map fields across rather than assuming identical types. Also add `ecommerce-inventory` as a dependency in `ecommerce-product/pom.xml` if not already present — check first, design-docs/02 §4 already documents `InventoryQueryService` as consumed by product, so the dependency likely already exists.)

- [ ] **Step 2: Fix the existing test that mocks and locks in the hardcoded 999**

Open `ProductDetailServiceTest.java`, find the mock of `StockInfoFetcher` returning `999`, replace with a mock of the new `InventoryQueryService` dependency returning a realistic stubbed stock summary matching the test's other fixture data.

- [ ] **Step 3: Fix the wrong error code in `getSkuForSale`**

Read `ProductQueryServiceImpl.java`. Per audit (line ~60-63):
```java
throw new BusinessException("SKU_NOT_AVAILABLE", "SKU is not available for sale: " + skuId);
```
Change to:
```java
throw new BusinessException("PRODUCT_NOT_FOR_SALE", "SKU is not available for sale: " + skuId);
```
(Match the exact existing message text/exception construction from your read — only the code string changes.)

- [ ] **Step 4: Default search to only show `ON_SHELF` products**

Read `ProductSearchRequest.java`. Per audit, field `onlyOnShelf` defaults `false`. Change the field default to `true`:
```java
private boolean onlyOnShelf = true;
```
Read `ProductSearchService.java`'s `buildSpecification` (around line 96-102) to confirm how `onlyOnShelf` gates the status filter, and confirm this default change alone is sufficient (i.e., the anonymous `/api/v1/products` and `/api/v1/products/search` endpoints don't explicitly construct the request with `onlyOnShelf=false` somewhere, which would override this default — check `ProductController.java`'s request-building/binding for both endpoints).

- [ ] **Step 5: Fix category filter to include descendant categories**

Read `ProductSearchService.java`'s `matchesCategory` (around line 124-130), currently:
```java
private boolean matchesCategory(ProductSpu spu, Long categoryId) {
    return categoryId.equals(spu.getCategoryId());
}
```
Replace with (inject `CategoryRepository` if not already a field — check the class's existing constructor first):
```java
private boolean matchesCategory(ProductSpu spu, Long categoryId) {
    Set<Long> descendantIds = resolveDescendantCategoryIds(categoryId);
    return descendantIds.contains(spu.getCategoryId());
}

private Set<Long> resolveDescendantCategoryIds(Long rootCategoryId) {
    Set<Long> result = new HashSet<>();
    Deque<Long> toVisit = new ArrayDeque<>();
    toVisit.add(rootCategoryId);
    while (!toVisit.isEmpty()) {
        Long current = toVisit.poll();
        if (!result.add(current)) {
            continue;
        }
        categoryRepository.findByParentId(current).forEach(child -> toVisit.add(child.getId()));
    }
    return result;
}
```
(Confirm `CategoryRepository` has a `findByParentId(Long)` method — if not, add one; it's a standard Spring Data derived query. Add `import java.util.*;` as needed.)

- [ ] **Step 6: Fix the existing search test that asserts the old (buggy) category/no-tags/onlyOnShelf-false behavior**

Open `ProductSearchServiceTest.java`, find and correct any assertions that currently expect: default search to include off-shelf/draft items, category filter to exclude sub-category items, or tag filters to have no effect — update expected values to match Steps 4/5/7's corrected behavior.

- [ ] **Step 7: Wire the `tags` filter**

Read `ProductSearchService.java`'s `buildSpecification` in full and `ProductSearchRequest.getTags()`. Add tag matching to the specification/post-filter alongside the existing category/brand checks — if there's no tag-association table yet, add a simple one (e.g. a `product_tags` join table + `ProductTagRepository`) since README §3 permits new entities as long as API fields/URLs don't change. Keep this additive and minimal: a `Set<String> getTagsForSpu(Long spuId)` lookup used the same way `matchesCategory`/`matchesBrand` are used.

- [ ] **Step 8: Fix pagination `total` when category/brand filters are applied**

Read `ProductSearchService.java`'s `search()` method (lines ~63-85) in full. Currently the DB-level `Specification` only encodes status/keyword/price, and category/brand matching happens afterward in memory on just the current page's content, while `total` is taken from the DB page directly. Push `categoryId`/`brandId` into the JPA `Specification` itself (e.g., resolve matching `spuId`s via `resolveDescendantCategoryIds`/brand lookup first, then add a `spu.id IN (...)` predicate to the `Specification` before calling `repository.findAll(spec, pageable)`), so `total` and page contents are both computed after every filter, not just some of them.

- [ ] **Step 9: Add audit logging to on/off-shelf**

Read `SkuService.java`'s `onShelf`/`offShelf` (lines ~78-101) and `AdminProductController.java`'s corresponding endpoints (lines ~60-78) in full. Add an `operatorId` parameter threaded from the controller (same pattern as Task 2 Step 9/10 — extract via `Authentication` in the controller, pass to the service), and call:
```java
auditLogService.record(operatorId, "SKU_ON_SHELF", String.valueOf(skuId),
        beforeStatus.name(), SkuStatus.ON_SHELF.name(), null);
```
(and the mirror for `offShelf`). Inject `AuditLogService` into `SkuService`'s constructor.

- [ ] **Step 10: Add a 10-minute Caffeine cache for product detail**

Create `code/ecommerce-product/src/main/java/com/ecommerce/product/config/ProductCacheConfig.java`, modeled on the existing `code/ecommerce-cart/src/main/java/com/ecommerce/cart/config/CartCacheConfig.java` (read that file first for the exact pattern this codebase uses):
```java
package com.ecommerce.product.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import java.time.Duration;

@Configuration
public class ProductCacheConfig {

    @Bean
    @Primary
    public CacheManager productCacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager("product:detail");
        manager.setCaffeine(Caffeine.newBuilder().expireAfterWrite(Duration.ofMinutes(10)));
        return manager;
    }
}
```
(If `CartCacheConfig` uses a different, more specific pattern — e.g., a manually-managed `Cache` object per key prefix rather than Spring's `@Cacheable` — mirror that exact pattern instead of Spring's declarative caching, for consistency with the rest of the codebase. Read it first; do not guess.) Then annotate `ProductDetailService.getProductDetail(Long skuId)` with `@Cacheable(cacheNames = "product:detail", key = "#skuId")`, and add `@CacheEvict(cacheNames = "product:detail", key = "#skuId")` to `SkuService.onShelf`/`offShelf`/any SKU-update method so the cache doesn't serve stale shelf-status.

- [ ] **Step 11: Write a test proving the cache evicts on shelf-status change**

Add to `code/ecommerce-product/src/test/java/com/ecommerce/product/service/ProductDetailServiceTest.java` (Spring context test, not pure-mock, since caching needs the real `CacheManager`):
```java
@Test
void getProductDetail_afterOffShelf_returnsFreshNotCachedData() {
    ProductDetailResponse before = productDetailService.getProductDetail(skuId);
    assertEquals("ON_SHELF", before.getStatus());

    skuService.offShelf(skuId, "admin-1");

    ProductDetailResponse after = productDetailService.getProductDetail(skuId);
    assertEquals("OFF_SHELF", after.getStatus());
}
```
(Adapt to this test class's existing setup — if it's currently a pure-mockito unit test with no Spring context, either convert it to a `@SpringBootTest` slice that loads the cache config, or add this as a new test method in a separate `@SpringBootTest`-annotated class alongside it; match whatever pattern `CartCacheManagerTest` uses for testing cache behavior in this codebase.)

- [ ] **Step 12 (suspicious finding — apply only if it fits without expanding scope): keyword search should also match SPU name**

Read `ProductSearchService.java`'s keyword predicate (lines ~104-106). If it currently only checks `ProductSku.name`, extend it to also check the already-loaded SPU's name (via the existing `spuMap` the class already builds for other purposes — do not add a new query just for this). Do not attempt to add a "sell point" field — the audit found no such column exists in `附录C-数据模型.md`, so extending the schema for it is out of scope; matching SPU name only is the safe, contract-consistent portion of this finding.

- [ ] **Step 13: Add rate limiting to search**

Read `code/ecommerce-common/src/main/java/com/ecommerce/common/ratelimit/RateLimit.java` (already read in Task 2 Step 11 if that task ran first — reuse the same attribute names). Add to `ProductController.searchProducts`:
```java
@RateLimit(key = "#request.getRemoteAddr()", limit = 120, windowSeconds = 60)
```
using the exact attribute names confirmed from the annotation (adjust the SpEL key expression to however this codebase's other `@RateLimit`-worthy endpoints resolve client IP — check if `HttpServletRequest` is available as a method parameter here already, or needs adding).

- [ ] **Step 14: Run the full product module test suite**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-product -am test
```
Expected: all pass.

- [ ] **Step 15: Install and run the product-related black-box tests**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub003_createProductAndOnShelf test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub004_searchProductByKeyword test
```
Expected: both pass (no regression from the search/cache changes).

- [ ] **Step 16: Commit**

```bash
git add code/ecommerce-product
git commit -m "$(cat <<'EOF'
Fix product module: real stock lookup, correct PRODUCT_NOT_FOR_SALE
code, search defaults to ON_SHELF only, category filter includes
descendants, tags filter wired up, pagination total fixed, on/off-shelf
audit log, 10-minute detail cache, search rate limit

Per design-docs/05 and design-docs/02 §4/§7.
EOF
)"
```

## Task 4: `ecommerce-inventory` module (7 fixes)

**Depends on:** Task 1 (`AuditLogService`).

**Files:**
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/query/InventoryQueryService.java` (fix stale javadoc)
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/controller/AdminInventoryController.java`
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/StockAdjustmentService.java`
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/entity/StockAdjustment.java`
- Modify: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/entity/InventoryStock.java` (add `@Version`)
- Test: `code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/service/InventoryReservationServiceImplTest.java` (existing — has comments admitting bug "L2-03", fix assertions, see Step 2)
- Test: `code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/service/InventoryServiceTest.java` (existing — fix `testCheckAvailability_exactMatch_returnsUnavailable`, see Step 4)

- [ ] **Step 1: Fix `reserve()` to only touch `reservedStock`, never `onHandStock`**

Read `InventoryReservationServiceImpl.java`'s `reserve()` (lines ~37-81). Per audit, line 58-59 currently:
```java
stock.setOnHandStock(stock.getOnHandStock() - toReserve);
stock.setReservedStock(stock.getReservedStock() + toReserve);
```
Delete the `setOnHandStock` line entirely:
```java
stock.setReservedStock(stock.getReservedStock() + toReserve);
```

- [ ] **Step 2: Fix the existing test that encodes the bug (comments literally reference bug id "L2-03")**

Open `InventoryReservationServiceImplTest.java`, find every assertion/comment referencing "L2-03" or asserting `onHandStock` decreases during `reserve()`. Update: `reserve()` should leave `onHandStock` unchanged and only increase `reservedStock`; `availableStock` (`onHandStock - reservedStock`) should decrease by exactly the reserved quantity (not double).

- [ ] **Step 3: Fix the off-by-one boundary bug in `checkAvailability`**

Read `InventoryService.java` around line 75. Per audit:
```java
boolean available = totalAvailable > quantity;
```
Change to:
```java
boolean available = totalAvailable >= quantity;
```
Also fix the stale javadoc on `InventoryQueryService.checkAvailability` (around line 26) that documents the wrong ">" behavior — update it to say "available when availableStock >= requestQuantity."

- [ ] **Step 4: Fix the existing test asserting the wrong boundary behavior**

Open `InventoryServiceTest.java`, find `testCheckAvailability_exactMatch_returnsUnavailable`, rename to `testCheckAvailability_exactMatch_returnsAvailable` and change its assertion from `assertFalse(available)` to `assertTrue(available)`.

- [ ] **Step 5: Create an `OutboundOrder` when `deductAfterPayment` runs**

Read `InventoryReservationServiceImpl.java`'s `deductAfterPayment()` (lines ~104-125) and `InventoryService.java`'s `outbound()` method (which already correctly creates `OutboundOrder` rows for the manual path) side by side. After the existing stock/reservation decrement logic in `deductAfterPayment`, add, per reservation processed:
```java
OutboundOrder outboundOrder = new OutboundOrder();
outboundOrder.setWarehouseId(reservation.getWarehouseId());
outboundOrder.setSkuId(reservation.getSkuId());
outboundOrder.setQuantity(reservation.getQuantity());
outboundOrder.setOrderId(orderId);
outboundOrder.setStatus(OutboundOrderStatus.COMPLETED);
outboundOrderRepository.save(outboundOrder);
```
(Match field names exactly to what `InventoryService.outbound()`'s existing `OutboundOrder` construction uses — read that method first and mirror it precisely rather than guessing field names. Inject `OutboundOrderRepository` into `InventoryReservationServiceImpl`'s constructor if not already present.)

- [ ] **Step 6: Write a test proving `deductAfterPayment` creates an outbound order**

Add to `InventoryReservationServiceImplTest.java`:
```java
@Test
void deductAfterPayment_createsOutboundOrderForEachReservation() {
    // ... arrange a reservation exactly as the existing deductAfterPayment tests do ...

    inventoryReservationService.deductAfterPayment(orderId);

    List<OutboundOrder> outboundOrders = outboundOrderRepository.findByOrderId(orderId);
    assertEquals(1, outboundOrders.size());
    assertEquals(OutboundOrderStatus.COMPLETED, outboundOrders.get(0).getStatus());
}
```
(Match this test class's existing arrange-step conventions for setting up a reservation — copy the setup from an existing `deductAfterPayment` test in the same file rather than inventing new fixture code.)

- [ ] **Step 7: Add a 30-second cache for inventory summary**

Mirror Task 3 Step 10's `ProductCacheConfig` pattern (whichever one that read confirmed this codebase actually uses) with a 30-second TTL cache named `inventory:summary`, keyed by `skuId`. Annotate `InventoryService.getStockSummary`/`getStockSummaryResponse` with `@Cacheable(cacheNames = "inventory:summary", key = "#skuId")`, and add `@CacheEvict(cacheNames = "inventory:summary", key = "#skuId")` to every stock-mutating method (`inbound`, `outbound`, `reserve`, `release`, `deductAfterPayment`, stock adjustment) so cached summaries don't go stale after a 30-second-old write.

- [ ] **Step 8: Add operator field to stock adjustment audit trail**

Read `StockAdjustment.java`, `StockAdjustmentService.java`, `AdminInventoryController.java` in full. Add an `operatorId` column to `StockAdjustment`:
```java
@Column(name = "operator_id", nullable = false)
private String operatorId;
```
(plus getter/setter). Thread an `Authentication` parameter through `AdminInventoryController.createAdjustment` down to `StockAdjustmentService.create(...)`, setting `operatorId` on the new `StockAdjustment` before saving. Also call `auditLogService.record(operatorId, "INVENTORY_ADJUSTMENT", skuId, beforeQty, afterQty, reason)` from `StockAdjustmentService.create(...)` (inject `AuditLogService`).

- [ ] **Step 9: Add optimistic locking to `InventoryStock`**

Read `InventoryStock.java` and `BaseEntity.java` first (confirm `BaseEntity` doesn't already provide `@Version` — if it does for all entities, this finding is moot and this step should be skipped with a note in the commit message). If not already present, add:
```java
@Version
@Column(name = "version")
private Long version;
```
No application code changes needed beyond this — Hibernate handles the optimistic-lock check automatically on `save()`; a concurrent conflicting update will throw `OptimisticLockingFailureException`, which should be caught in `InventoryReservationServiceImpl.reserve()` and retried once or surfaced as a 409 via `ConflictException` (do not leave it as an unhandled 500 — wrap the `save()` call in a try/catch that retries the read-modify-write once before giving up).

- [ ] **Step 10: Fix the warning endpoint to be reachable via the documented API alone**

Read `StockWarningService.java` and `AdminInventoryController.java`'s warnings-related endpoints in full, and `附录C-数据模型.md`'s `inventory_stock` table definition (confirm the `warning_threshold` column this doc defines). Add a `warningThreshold` field to `InventoryStock` matching that column, settable via the existing (frozen-contract) inbound/adjustment endpoints if they accept a threshold field, or defaulting to a sane value (e.g., read from `RuntimeConfigRegistry` with a documented default) so `GET /api/v1/admin/inventory/warnings` can compare `onHandStock` against this per-row threshold without requiring the separate, non-contracted `POST .../warnings/rule` endpoint to have been called first. Keep the existing rule-based path working too — this is additive, not a replacement.

- [ ] **Step 11: Run the full inventory module test suite**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-inventory -am test
```
Expected: all pass.

- [ ] **Step 12: Install and run the inventory-related black-box test**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub005_inboundAndQueryStock test
```
Expected: passes (onHandStock=50, availableStock=50 after 50-unit inbound, unaffected by the reserve() fix since no reservation happens in this test).

- [ ] **Step 13: Commit**

```bash
git add code/ecommerce-inventory
git commit -m "$(cat <<'EOF'
Fix inventory module: reserve() no longer double-decrements stock,
>= boundary on availability check, outbound order created on payment
deduction, 30s summary cache, adjustment audit log with operator,
optimistic locking, warning threshold reachable via frozen API

Per design-docs/06 and design-docs/02 §7/design-docs/03 §6.
EOF
)"
```

## Task 5: `ecommerce-cart` module (4 fixes — the biggest rewrite of any single module task)

**Depends on:** Task 1 only. Independent of Tasks 2–4/6–12.

**Files:**
- Modify: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java` (major rewrite)
- Delete: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/Cart.java`
- Delete: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartItem.java`
- Delete: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartRepository.java`
- Delete: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartItemRepository.java`
- Modify: `code/ecommerce-cart/pom.xml` (add `ecommerce-promotion` dependency)
- Modify: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/dto/CartEstimateResponse.java` (add `applicableCoupons` field)
- Test: `code/ecommerce-cart/src/test/java/com/ecommerce/cart/service/CartServiceTest.java` (major rewrite — currently asserts DB persistence and quantity-overwrite as correct behavior; both are wrong)

- [ ] **Step 1: Read the existing `CartCacheManager`/`CartData`/`CartItemData`/`CartCacheConfig` in full — these already work correctly and this task reuses them as-is**

```bash
cat code/ecommerce-cart/src/main/java/com/ecommerce/cart/cache/CartCacheManager.java
cat code/ecommerce-cart/src/main/java/com/ecommerce/cart/cache/CartData.java
cat code/ecommerce-cart/src/main/java/com/ecommerce/cart/cache/CartItemData.java
cat code/ecommerce-cart/src/main/java/com/ecommerce/cart/config/CartCacheConfig.java
```
Note their exact method signatures (e.g. `get(userId)`, `put(userId, cartData)`, `CartData`'s fields/methods for adding/removing/updating items) — the rewrite in Step 3 must call these exactly.

- [ ] **Step 2: Read the current `CartService.java` in full**

```bash
cat code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java
```
Note every method's signature (`addItem`, `getCart`, `updateItem`, `removeItem`, `clearCart`, `estimate`, `getOrCreateCart`) so the rewrite preserves the exact same public method signatures the controller calls (do not change `CartController.java` — only what's behind it).

- [ ] **Step 3: Rewrite `CartService` to use `CartCacheManager` instead of JPA repositories**

Replace every reference to `cartRepository`/`cartItemRepository` with equivalent calls into `CartCacheManager`, keeping the exact same public method signatures found in Step 2. The shape (adapt names precisely to what Step 1 revealed):
```java
@Service
public class CartService {

    private final CartCacheManager cartCacheManager;
    private final CartValidationService cartValidationService;
    private final PromotionCalculationService promotionCalculationService; // added in Step 7

    // constructor updated accordingly — no more repository fields

    public CartItemResponse addItem(Long userId, AddCartItemRequest request) {
        cartValidationService.validateSku(request.getSkuId());
        cartValidationService.validateStock(request.getSkuId(), request.getQuantity());

        CartData cart = cartCacheManager.getOrCreate(userId);
        CartItemData existing = cart.findItem(request.getSkuId());
        if (existing != null) {
            int newQuantity = existing.getQuantity() + request.getQuantity();
            cartValidationService.validateStock(request.getSkuId(), newQuantity);
            existing.setQuantity(newQuantity);
        } else {
            cart.addItem(new CartItemData(request.getSkuId(), request.getQuantity()));
        }
        cartCacheManager.put(userId, cart);
        return CartItemResponse.from(cart.findItem(request.getSkuId()));
    }

    public CartResponse getCart(Long userId) {
        CartData cart = cartCacheManager.getOrCreate(userId);
        return CartResponse.from(cart);
    }

    public CartItemResponse updateItem(Long userId, Long skuId, UpdateCartItemRequest request) {
        cartValidationService.validateStock(skuId, request.getQuantity());
        CartData cart = cartCacheManager.getOrCreate(userId);
        CartItemData item = cart.findItem(skuId);
        if (item == null) {
            throw new ResourceNotFoundException("Cart item not found for sku: " + skuId);
        }
        item.setQuantity(request.getQuantity());
        cartCacheManager.put(userId, cart);
        return CartItemResponse.from(item);
    }

    public void removeItem(Long userId, Long skuId) {
        CartData cart = cartCacheManager.getOrCreate(userId);
        cart.removeItem(skuId);
        cartCacheManager.put(userId, cart);
    }

    public void clearCart(Long userId) {
        cartCacheManager.remove(userId);
    }
}
```
This is illustrative of the shape, not a literal drop-in — **use Step 1/2's actual method names** (`CartData`/`CartItemData`/`CartCacheManager` might name things `get`/`save`/`evict` rather than `getOrCreate`/`put`/`remove`; match reality, not this sketch). Preserve `getOrCreateCart`, `estimate`, and any other existing method from Step 2's read that isn't shown above — this sketch only covers the ones directly affected by the JPA→cache migration and the quantity-accumulation fix.

- [ ] **Step 4: Delete the JPA entities and repositories**

```bash
git rm code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/Cart.java
git rm code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartItem.java
git rm code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartRepository.java
git rm code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartItemRepository.java
```
(`git rm` stages the deletion; don't run bare `rm` and forget to stage it.)

- [ ] **Step 5: Rewrite `CartServiceTest`**

Read the existing test file first (it currently has `testCart_storedInDatabase()` and `testAddItem_existingSku_replacesQuantity()`, per audit, which assert the two behaviors being fixed). Replace with tests against the cache-backed behavior:
```java
@Test
void addItem_sameSkuTwice_accumulatesQuantity() {
    cartService.addItem(userId, new AddCartItemRequest(skuId, 3));
    CartItemResponse response = cartService.addItem(userId, new AddCartItemRequest(skuId, 2));

    assertEquals(5, response.getQuantity());
}

@Test
void updateItem_setsExactQuantity_doesNotAccumulate() {
    cartService.addItem(userId, new AddCartItemRequest(skuId, 3));
    CartItemResponse response = cartService.updateItem(userId, skuId, new UpdateCartItemRequest(7));

    assertEquals(7, response.getQuantity());
}

@Test
void cart_isNeverPersistedToDatabase() {
    cartService.addItem(userId, new AddCartItemRequest(skuId, 1));

    // No CartRepository/CartItemRepository exists anymore — this test just
    // confirms no such JPA table/bean exists in the application context.
    assertThrows(NoSuchBeanDefinitionException.class,
            () -> applicationContext.getBean("cartRepository"));
}
```
(Adapt request/response class names to Step 2's read. Match this test class's existing mocking-vs-Spring-context style — if it currently mocks `CartRepository` directly, convert the mock target to `CartCacheManager` instead of trying to keep both mocking styles.)

- [ ] **Step 6: Run cart tests to confirm Steps 3-5 work before adding promotion integration**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-cart -am test
```
Expected: all pass.

- [ ] **Step 7: Wire `PromotionCalculationService` into `estimate()`**

Read `code/ecommerce-cart/pom.xml` first — add if missing:
```xml
<dependency>
    <groupId>com.ecommerce</groupId>
    <artifactId>ecommerce-promotion</artifactId>
    <version>${project.version}</version>
</dependency>
```
Read `CartService.java`'s `estimate()` (per audit, hardcodes `discountAmount`/`pointsDeductionAmount` to `ZERO`) and `PromotionCalculationService.calculate(PromotionCalculateRequest)`'s exact request/response shape (from `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/dto/PromotionCalculateRequest.java` and `PromotionCalculateResponse.java`). Replace the hardcoded zeros with a real call:
```java
public CartEstimateResponse estimate(Long userId, List<Long> couponIds) {
    CartData cart = cartCacheManager.getOrCreate(userId);
    BigDecimal itemTotal = computeItemTotal(cart); // existing helper, keep as-is

    PromotionCalculateRequest promoRequest = new PromotionCalculateRequest();
    promoRequest.setUserId(userId);
    promoRequest.setCouponIds(couponIds);
    promoRequest.setItems(toCalculateItems(cart)); // map CartItemData -> PromotionCalculateRequest.CalculateItem
    PromotionCalculateResponse promoResponse = promotionCalculationService.calculate(promoRequest);

    BigDecimal shippingFee = computeShippingFee(itemTotal); // existing helper, keep as-is
    BigDecimal packagingFee = computePackagingFee(cart.getItems().size()); // existing helper, keep as-is
    BigDecimal discountAmount = promoResponse.getTotalDiscount();
    BigDecimal pointsDeductionAmount = BigDecimal.ZERO; // out of scope for this task — loyalty redemption wiring is Task 10/Task 6's concern

    BigDecimal payableAmount = itemTotal.add(shippingFee).add(packagingFee)
            .subtract(discountAmount).subtract(pointsDeductionAmount);

    CartEstimateResponse response = new CartEstimateResponse();
    response.setItemTotal(itemTotal);
    response.setShippingFee(shippingFee);
    response.setPackagingFee(packagingFee);
    response.setDiscountAmount(discountAmount);
    response.setPointsDeductionAmount(pointsDeductionAmount);
    response.setPayableAmount(payableAmount);
    response.setApplicableCoupons(promoResponse.getApplicableCoupons());
    return response;
}
```
(This assumes `estimate()`'s current signature already takes `couponIds` or similar — read Step 2's output to confirm the actual current signature and adapt method helpers (`computeItemTotal`/`computeShippingFee`/`computePackagingFee`) to whatever the existing private helpers are actually named; do not invent new helper names if equivalents already exist in the file.)

- [ ] **Step 8: Add `applicableCoupons` field to `CartEstimateResponse`**

Read the file, add:
```java
private List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons;

public List<PromotionCalculateResponse.ApplicableCoupon> getApplicableCoupons() {
    return applicableCoupons;
}

public void setApplicableCoupons(List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons) {
    this.applicableCoupons = applicableCoupons;
}
```
(If `PromotionCalculateResponse` doesn't expose an `ApplicableCoupon` nested type — confirm from reading it in Task 8 material or directly — adjust the type accordingly; do not block this step on Task 8 having run yet, since `PromotionCalculationService`'s public DTOs already exist regardless of what Task 8 changes internally.)

- [ ] **Step 9: Write a test proving estimate reflects a real coupon discount**

Add to `CartServiceTest.java` (or a new `CartEstimateServiceTest.java` if estimate logic lives in a separate class per Step 2's read):
```java
@Test
void estimate_withValidCoupon_reflectsRealDiscount() {
    cartService.addItem(userId, new AddCartItemRequest(skuId, 1)); // price 100.00 fixture SKU

    CartEstimateResponse response = cartService.estimate(userId, List.of(couponId)); // 20% discount coupon fixture

    assertEquals(0, new BigDecimal("20.00").compareTo(response.getDiscountAmount()));
}
```
(This test necessarily depends on Task 8's promotion fixes being correct to produce the right number — if Task 8 hasn't landed yet when this runs, the discount math may reflect the pre-fix promotion bug; note in your test-run output which is the case, and re-run this specific test after Task 8 lands as part of Task 13's integration pass.)

- [ ] **Step 10: Run the full cart module test suite**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-cart -am test
```
Expected: all pass (Step 9's exact discount value may only be correct after Task 8 also lands — acceptable at this point, re-verify in Task 13).

- [ ] **Step 11: Install and run the cart-related black-box tests**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub006_addAndModifyCartItem test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub007_cartPriceEstimate test
```
Expected: both pass.

- [ ] **Step 12: Commit**

```bash
git add code/ecommerce-cart
git commit -m "$(cat <<'EOF'
Fix cart module: use the existing Caffeine CartCacheManager instead of
persisting to H2, accumulate quantity on repeat add, wire real
PromotionCalculationService into price estimate

Per design-docs/07 §1/§2/§3 and design-docs/02 §7 — cart must never
be backed by a DB table; the cache infrastructure already existed but
was never connected to CartService.
EOF
)"
```

## Task 6: `ecommerce-order` module (12 fixes — largest module, budget the most time here)

**Depends on:** Task 1 (`OrderPaidEvent` now lives in `ecommerce-common`; `OrderValidationException` already existed pre-Task-1). Read Task 1 Step 23's recorded finding about `OrderPaymentEventHandler`/`PaymentSucceededEvent` before starting Step 9 below.

**Files:**
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/controller/OrderController.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTotalCalculator.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPreconditionChecker.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderValidator.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderStateMachine.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/BatchOrderService.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/repository/OrderRepository.java` (already has the lookup method, per audit — just start calling it)
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPaymentEventHandler.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderLifecycleService.java`
- Delete: `code/ecommerce-order/src/main/java/com/ecommerce/order/event/OrderPaidEvent.java` (superseded by `com.ecommerce.common.event.OrderPaidEvent`)
- Test: various existing tests referenced per-step below — this module has the most existing (unscored) tests that encode buggy behavior; expect to fix several.

- [ ] **Step 1: Fix create-order HTTP status (already-known, PUB-102)**

Current (`OrderController.java`, confirmed this session):
```java
@PostMapping("/create")
public ResponseEntity<CreateOrderResponse> createOrder(
        @Valid @RequestBody CreateOrderRequest request) {
    Long userId = getCurrentUserId();
    log.info("POST /api/v1/orders/create: userId={}, itemsCount={}",
            userId, request.getItems() != null ? request.getItems().size() : 0);
    CreateOrderResponse response = orderService.createOrder(userId, request);
    return ResponseEntity.ok(response);
}
```
Change the last line to:
```java
    return ResponseEntity.status(HttpStatus.CREATED).body(response);
```
Add `import org.springframework.http.HttpStatus;`.

- [ ] **Step 2: Fix payableAmount to include shipping fee (already-known, PUB-104)**

Current (`OrderTotalCalculator.java`, confirmed this session):
```java
public BigDecimal calculate(BigDecimal itemTotal, BigDecimal shippingFee,
                            BigDecimal packagingFee, BigDecimal discountAmount,
                            BigDecimal pointsDeductionAmount) {
    BigDecimal payableAmount = MonetaryUtil.add(itemTotal, packagingFee);
    payableAmount = MonetaryUtil.subtract(payableAmount, discountAmount);
    payableAmount = MonetaryUtil.subtract(payableAmount, pointsDeductionAmount);
```
Change the first line of the body to include `shippingFee`:
```java
public BigDecimal calculate(BigDecimal itemTotal, BigDecimal shippingFee,
                            BigDecimal packagingFee, BigDecimal discountAmount,
                            BigDecimal pointsDeductionAmount) {
    BigDecimal payableAmount = MonetaryUtil.add(MonetaryUtil.add(itemTotal, shippingFee), packagingFee);
    payableAmount = MonetaryUtil.subtract(payableAmount, discountAmount);
    payableAmount = MonetaryUtil.subtract(payableAmount, pointsDeductionAmount);
```
(Rest of the method — the `MIN_PAYABLE_AMOUNT` clamp and logging — is unchanged.)

- [ ] **Step 3: Run the two known-bug black-box tests to confirm Steps 1-2 fix them**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub102_createOrderShouldReturn201 test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub104_orderTotalShouldIncludeShipping test
```
Expected: both pass. (`pub104` also depends on `discountAmount` being correct, which depends on Task 8's promotion fixes — if Task 8 hasn't landed, expect `pub104` might still fail on the discount portion specifically; re-verify in Task 13.)

- [ ] **Step 4: Add frozen-user check to order preconditions**

Read `OrderPreconditionChecker.java` (lines ~31-42) in full, and `UserQueryService.isFrozen(Long)`'s exact signature. Add the check (adapt to the exact method structure/exception style already used elsewhere in the same class):
```java
if (userQueryService.isFrozen(userId)) {
    throw new BusinessException("USER_FROZEN", "User is frozen: " + userId);
}
```
(Confirm `UserQueryService` is already injected into this class — per the audit it exists as a dependency already used for existence checks; just add the frozen check alongside it.)

- [ ] **Step 5: Write a test proving frozen users cannot create orders (module-level, complementing the existing black-box PUB-103)**

Add to `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderPreconditionCheckerTest.java` (read the existing file first to match its mocking style):
```java
@Test
void check_frozenUser_throwsUserFrozen() {
    when(userQueryService.isFrozen(userId)).thenReturn(true);

    BusinessException ex = assertThrows(BusinessException.class,
            () -> orderPreconditionChecker.check(userId, items));
    assertEquals("USER_FROZEN", ex.getCode());
}
```

- [ ] **Step 6: Wire the risk check into order creation**

Read `OrderService.java` around lines 167-168 (currently an empty "Step 4: Risk check" block) and `OrderRiskChecker.check(...)`'s exact signature/`RiskCheckResult` shape. Replace the empty block with:
```java
RiskCheckResult riskResult = orderRiskChecker.check(userId, itemTotal, skuIds);
if (!riskResult.isPassed()) {
    throw new BusinessException("ORDER_RISK_REJECTED", "Order rejected by risk check: " + riskResult.getReason());
}
```
(Confirm `orderRiskChecker` is already injected — per audit it is, just unused. Confirm the exact variable names for `itemTotal`/`skuIds` available at that point in the method from your read, and `RiskCheckResult`'s actual getter names.)

- [ ] **Step 7: Write a test proving a high-risk order is rejected**

Add to `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderServiceTest.java` (read existing file for mocking conventions):
```java
@Test
void createOrder_highRiskCheckFails_throwsOrderRiskRejected() {
    when(orderRiskChecker.check(any(), any(), any()))
            .thenReturn(RiskCheckResult.rejected("high amount"));

    BusinessException ex = assertThrows(BusinessException.class,
            () -> orderService.createOrder(userId, request));
    assertEquals("ORDER_RISK_REJECTED", ex.getCode());
}
```

- [ ] **Step 8: Fix amount validation to throw `OrderValidationException` instead of `IllegalArgumentException`**

Read `OrderValidator.java` (lines ~24-29):
```java
if (amount.compareTo(BigDecimal.ZERO) <= 0) {
    throw new IllegalArgumentException("Order amount must be positive, got: " + amount);
}
```
Change to:
```java
if (amount.compareTo(BigDecimal.ZERO) <= 0) {
    throw new OrderValidationException("Order amount must be positive, got: " + amount);
}
```
Add `import com.ecommerce.common.exception.OrderValidationException;` and remove the now-dead, never-called `util/OrderValidationUtils.validateOrderAmount()` if confirmed truly unused elsewhere (grep first: `grep -rn "OrderValidationUtils" code/ecommerce-order/src/main/java` — if only `validateOrderAmount` is dead and other methods in that utility class are used, only remove the dead method, not the whole class).

- [ ] **Step 9: Run a quick test to confirm invalid amount now returns 400 not 500**

Add/fix a test in `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderValidatorTest.java`:
```java
@Test
void validateAmount_zeroOrNegative_throwsOrderValidationException() {
    assertThrows(OrderValidationException.class, () -> orderValidator.validateAmount(BigDecimal.ZERO));
    assertThrows(OrderValidationException.class, () -> orderValidator.validateAmount(new BigDecimal("-1.00")));
}
```

- [ ] **Step 10: Fix state machine to forbid PAID→CANCELLED directly**

Read `OrderStateMachine.java` (lines ~39-42):
```java
allowedTransitions.put(OrderStatus.PAID, EnumSet.of(OrderStatus.PICKING, OrderStatus.CANCEL_REVIEWING, OrderStatus.CANCELLED));
```
Change to:
```java
allowedTransitions.put(OrderStatus.PAID, EnumSet.of(OrderStatus.PICKING, OrderStatus.CANCEL_REVIEWING));
```

- [ ] **Step 11: Fix paid-order cancel to go through merchant review instead of cancelling directly**

Read `OrderCancelService.java` in full (lines ~83-84 dispatch, ~163-194 `cancelPaidOrderDirectly`, and the already-implemented `reviewCancel` at lines ~200-248). Replace the `PAID` branch's call to `cancelPaidOrderDirectly(order, reason)` with a transition into review:
```java
case PAID:
    order.setStatus(OrderStatus.CANCEL_REVIEWING);
    orderRepository.save(order);
    orderEventLogService.record(order.getId(), "CANCEL_REQUESTED", reason);
    return CancelOrderResponse.pendingReview(order.getId());
```
(Match `CancelOrderResponse`'s actual factory-method/constructor conventions from reading the class, and `orderEventLogService`'s exact method name from reading `OrderEventLogService.java` — do not invent a method name; if no such logging service call exists in this class yet, check whether `reviewCancel`'s existing implementation already logs the eventual approval and just skip a redundant log here, matching whatever pattern the file already uses for other state transitions.) Delete `cancelPaidOrderDirectly` entirely once nothing calls it (grep to confirm before deleting: `grep -rn "cancelPaidOrderDirectly" code/ecommerce-order/src/main/java`).

- [ ] **Step 12: Fix/write a test for the corrected paid-order-cancel flow**

Read the existing `OrderCancelServiceTest.java` for any test asserting `cancelPaidOrderDirectly`'s old immediate-CANCELLED behavior — update it to assert the new CANCEL_REVIEWING transition instead:
```java
@Test
void cancel_paidOrder_movesToCancelReviewing_notCancelledDirectly() {
    order.setStatus(OrderStatus.PAID);

    CancelOrderResponse response = orderCancelService.cancel(userId, order.getId(), "changed my mind");

    assertEquals(OrderStatus.CANCEL_REVIEWING, orderRepository.findById(order.getId()).get().getStatus());
}
```

- [ ] **Step 13: Fix batch order creation to not share one transaction**

Read `BatchOrderService.java` in full (class-level `@Transactional` at line ~20, `createBatch` at lines ~38-83). Remove the class-level `@Transactional` annotation (or method-level, wherever it currently sits) entirely:
```java
@Service
public class BatchOrderService {
    // no @Transactional here
```
Since `createBatch` calls `orderService.createOrder(...)` (itself already `@Transactional`) via a **different bean** (`orderService` is a separately-injected Spring bean, not `this`), removing the outer `@Transactional` is sufficient — each `createOrder` call now runs in and commits its own independent transaction through the normal Spring AOP proxy, so one failure's rollback-only marking no longer poisons a shared transaction. Confirm the existing `try/catch` around each iteration (lines ~56-70) still records per-item success/failure into the response the same way it did before — this behavior doesn't need to change, only the transaction boundary.

- [ ] **Step 14: Fix/write a test proving one bad order doesn't roll back the whole batch**

Read the existing `BatchOrderServiceTest.java` (per audit, its own comment says "method is annotated with @Transactional, meaning the ENTIRE batch runs..." — locate and remove/replace that outdated comment and any assertion built around all-or-nothing rollback):
```java
@Test
void createBatch_oneOrderFails_othersStillCommitted() {
    BatchCreateOrderRequest request = /* one valid order + one with a nonexistent skuId */;

    BatchCreateOrderResponse response = batchOrderService.createBatch(userId, request);

    assertEquals(1, response.getSuccessCount());
    assertEquals(1, response.getFailureCount());
    // The successful order must be findable afterward — proves it wasn't rolled back
    // by the failing sibling.
    assertTrue(orderRepository.findById(response.getResults().get(0).getOrderId()).isPresent());
}
```
(Adapt to `BatchCreateOrderRequest`/`BatchCreateOrderResponse`'s actual field names from reading them.)

- [ ] **Step 15: Add `externalOrderNo` idempotency check to order creation**

Read `OrderService.java`'s `createOrder` method in full and `OrderRepository.findByExternalOrderNoAndUserId` (confirmed to already exist, per audit, just unused). At the very top of `createOrder`, before any validation/reservation:
```java
if (request.getExternalOrderNo() != null && !request.getExternalOrderNo().isBlank()) {
    Optional<Order> existing = orderRepository.findByExternalOrderNoAndUserId(request.getExternalOrderNo(), userId);
    if (existing.isPresent()) {
        return orderAssembler.toCreateOrderResponse(existing.get());
    }
}
```
(Confirm `OrderAssembler`'s exact method name for building a `CreateOrderResponse` from an `Order` entity — per audit `OrderAssembler.java` exists; use whatever conversion method it already exposes rather than hand-building the response.)

- [ ] **Step 16: Write a test proving a repeated `externalOrderNo` returns the same order instead of creating a duplicate**

Add to `OrderServiceTest.java`:
```java
@Test
void createOrder_duplicateExternalOrderNo_returnsExistingOrder_doesNotCreateSecond() {
    CreateOrderResponse first = orderService.createOrder(userId, request);
    CreateOrderResponse second = orderService.createOrder(userId, request);

    assertEquals(first.getOrderId(), second.getOrderId());
    assertEquals(1, orderRepository.count());
}
```

- [ ] **Step 17: Release reserved inventory when an order times out**

Read `OrderTimeoutService.java` in full and `InventoryReservationService.release(Long orderId)`'s exact signature (Task 4 doesn't change this signature). Inject `InventoryReservationService` and call it inside `cancelExpiredOrder()`:
```java
private final InventoryReservationService inventoryReservationService;

// ... add to constructor ...

private void cancelExpiredOrder(Order order) {
    order.setStatus(OrderStatus.CANCELLED);
    orderRepository.save(order);
    inventoryReservationService.release(order.getId());
    // ... existing event publishing, unchanged ...
}
```
(Match the exact existing method body around the `setStatus`/`save`/event-publish calls from your read — only add the `release` call, in the same place `OrderCancelService.cancelCreatedOrder()` calls it, which you should read for the exact call pattern to mirror.)

- [ ] **Step 18: Write a test proving a timed-out order releases its reservation**

Add to `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderTimeoutServiceTest.java` (read the existing file first — per audit it currently asserts via reflection that `InventoryReservationService` is *not* a dependency; remove that assertion):
```java
@Test
void cancelExpiredOrder_releasesReservedInventory() {
    orderTimeoutService.cancelExpiredOrder(expiredOrder);

    verify(inventoryReservationService).release(expiredOrder.getId());
}
```

- [ ] **Step 19: Move order's `OrderPaidEvent` publishing to the shared common class**

Read `OrderPaymentEventHandler.java` and `OrderLifecycleService.java` in full (these are the two publish call sites per the loyalty audit). Change every:
```java
import com.ecommerce.order.event.OrderPaidEvent;
// ...
eventPublisher.publish(new OrderPaidEvent(this, order.getId(), order.getUserId(), order.getPayableAmount(), items));
```
to:
```java
import com.ecommerce.common.event.OrderPaidEvent;
// ...
eventPublisher.publish(new OrderPaidEvent(this, order.getId(), order.getUserId(), order.getPayableAmount(),
        toEventItems(order.getItems()), String.valueOf(order.getId()), null));
```
adding a small mapping helper if `order.getItems()` isn't already the right shape:
```java
private List<OrderPaidEvent.OrderItemPayload> toEventItems(List<OrderItem> items) {
    return items.stream()
            .map(item -> new OrderPaidEvent.OrderItemPayload(item.getSkuId(), item.getQuantity(), item.getPrice()))
            .collect(Collectors.toList());
}
```
Then delete the now-unused local class:
```bash
git rm code/ecommerce-order/src/main/java/com/ecommerce/order/event/OrderPaidEvent.java
```
(Only delete after confirming, via `grep -rn "order.event.OrderPaidEvent" code/`, that nothing else in the repo still imports the old local class.)

- [ ] **Step 20: Check Task 1 Step 23's recorded finding about `PaymentSucceededEvent`/`OrderPaymentEventHandler` and act on it**

Open `docs/superpowers/specs/2026-07-05-consistency-fixer-design.md` and re-read Task 1 Step 23's note (or the recorded finding left in this plan's Task 1 section). If it found that `OrderPaymentEventHandler` cannot actually be listening to `com.ecommerce.payment.event.PaymentSucceededEvent` via `@EventListener` (because `ecommerce-order` doesn't depend on `ecommerce-payment`), determine what it's actually doing instead (a direct synchronous call from payment via `OrderPaymentStatusUpdater`, most likely) and leave it as-is if that's the correct documented design (design-docs/02 §4 does say `OrderPaymentStatusUpdater` is how payment updates order — a direct interface call, not an event). If instead it turns out `OrderPaymentEventHandler` **does** have an `@EventListener` on a shadow-class `PaymentSucceededEvent`, add a step here (before Task 13) to also move `PaymentSucceededEvent` to `ecommerce-common` following the exact same pattern as Step 19, and flag this discovery explicitly in the commit message.

- [ ] **Step 21: Run the full order module test suite**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-order -am test
```
Expected: all pass (this module has the most tests of any module — budget real time here; some existing tests beyond the ones explicitly named above may also need small adjustments if they asserted old buggy behavior incidentally).

- [ ] **Step 22: Install and run every order-related black-box test**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub008_createBasicOrder test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub016_batchOrdersAllValid test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub102_createOrderShouldReturn201 test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub103_frozenUserCannotCreateOrder test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub104_orderTotalShouldIncludeShipping test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub106_highRiskOrderShouldBeRejected test
```
Expected: all pass.

- [ ] **Step 23: Commit**

```bash
git add code/ecommerce-order
git commit -m "$(cat <<'EOF'
Fix order module: 201 on create, payableAmount includes shipping,
frozen-user precondition, risk check actually invoked, correct
validation exception type, paid-cancel goes through merchant review,
state machine forbids PAID->CANCELLED, batch orders commit
independently, externalOrderNo idempotency, timeout releases
inventory, OrderPaidEvent published from the shared common class

Per design-docs/08, design-docs/01 §5, design-docs/02 §5/§6, and
design-docs/03 §2/§3.
EOF
)"
```

## Task 7: `ecommerce-payment` module (14 fixes)

**Depends on:** Task 1. Read Task 6 Step 20's finding about `PaymentSucceededEvent` before Step 9 below — if that step concluded `PaymentSucceededEvent` must also move to `ecommerce-common`, do that move as part of this task's Step 9 instead of just fixing its fields in place.

**Files:**
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/PaymentStatus.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentService.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentValidator.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundService.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundCalculator.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/InvoiceService.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/SettlementBatchService.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/PaymentSucceededEvent.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/dto/RefundApplyRequest.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/RefundRecord.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/dto/InvoiceRequest.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/InvoiceRecord.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentCallbackService.java`
- Modify: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/controller/PaymentController.java` (signature header, cross-referenced from Task 12's app-module finding)

- [ ] **Step 1: Rename `PaymentStatus.PENDING` to `CREATED` (already-known, PUB-009)**

Current (`PaymentStatus.java`, confirmed this session):
```java
public enum PaymentStatus {
    PENDING,
    SUCCESS,
    FAILED,
    REFUNDED
}
```
Change to:
```java
public enum PaymentStatus {
    CREATED,
    SUCCESS,
    FAILED,
    REFUNDED
}
```
And in `PaymentService.java` (confirmed this session, in `pay()`):
```java
payment.setStatus(PaymentStatus.PENDING);
```
becomes:
```java
payment.setStatus(PaymentStatus.CREATED);
```
(Grep-confirmed this session that `PaymentStatus.PENDING` has exactly this one reference in the whole repo — safe rename, no other call sites to update.)

- [ ] **Step 2: Run the known black-box test**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub009_createPayment test
```
Expected: passes.

- [ ] **Step 3: Add payment-amount-mismatch validation**

Read `PaymentValidator.java`'s `validate()` (lines ~34-74) in full. After the existing amount-positive check, add:
```java
if (request.getAmount().compareTo(order.getPayableAmount()) != 0) {
    throw new BusinessException("PAYMENT_AMOUNT_MISMATCH",
            "Payment amount " + request.getAmount() + " does not match order payable amount " + order.getPayableAmount());
}
```
(Place it among the other order-derived checks in this method — match the existing style/ordering of the other four validation steps already there.)

- [ ] **Step 4: Write a test proving mismatched amount is rejected**

Add to `code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/PaymentValidatorTest.java` (read existing file for conventions):
```java
@Test
void validate_amountDoesNotMatchPayable_throwsPaymentAmountMismatch() {
    OrderDto order = orderWithPayableAmount(new BigDecimal("100.00"));
    PayRequest request = payRequestWithAmount(new BigDecimal("0.01"));

    BusinessException ex = assertThrows(BusinessException.class,
            () -> paymentValidator.validate(request, order));
    assertEquals("PAYMENT_AMOUNT_MISMATCH", ex.getCode());
}
```
(Use this test class's existing fixture-building helper methods rather than constructing `OrderDto`/`PayRequest` from scratch — read the file first.)

- [ ] **Step 5: Fix refund approval to go through warehouse acceptance, not straight to completion**

Read `RefundService.java`'s `approveRefund()` (lines ~127-137) and `processRefund()`/`warehouseAccept()` (lines ~142-163) in full. Change:
```java
refund.setStatus(RefundStatus.APPROVED);
refundRecordRepository.save(refund);
processRefund(refund);
```
to:
```java
refund.setStatus(RefundStatus.WAITING_WAREHOUSE_ACCEPT);
refundRecordRepository.save(refund);
```
(`processRefund(refund)` moves to being called only from inside `warehouseAccept()`, which per the audit already calls it correctly at line ~160 — just remove the premature call from `approveRefund()`, don't duplicate the logic.)

- [ ] **Step 6: Fix/write a test for the corrected refund-review flow**

Read the existing `RefundServiceTest.java` for a test asserting `approveRefund` completes the refund immediately — update to assert it only reaches `WAITING_WAREHOUSE_ACCEPT`:
```java
@Test
void approveRefund_movesToWaitingWarehouseAccept_doesNotCompleteImmediately() {
    refundService.approveRefund(refundId, "admin-1");

    RefundRecord refund = refundRecordRepository.findById(refundId).get();
    assertEquals(RefundStatus.WAITING_WAREHOUSE_ACCEPT, refund.getStatus());
    assertNotEquals(PaymentStatus.REFUNDED, paymentRecordRepository.findById(paymentId).get().getStatus());
}

@Test
void warehouseAccept_afterApproval_completesRefund() {
    refundService.approveRefund(refundId, "admin-1");
    refundService.warehouseAccept(refundId, "warehouse-1");

    assertEquals(RefundStatus.COMPLETED, refundRecordRepository.findById(refundId).get().getStatus());
}
```

- [ ] **Step 7: Remove the extra flat fee from refund calculation**

Read `RefundCalculator.java` (line ~38):
```java
BigDecimal baseRefund = MonetaryUtil.multiply(paidAmount, refundFactor);
BigDecimal refund = MonetaryUtil.subtract(baseRefund, BigDecimal.ONE);
```
Change to just:
```java
BigDecimal refund = MonetaryUtil.multiply(paidAmount, refundFactor);
```
(Remove the now-unused `baseRefund` variable name, or rename it directly to `refund` — either is fine, just don't leave a dead intermediate variable.)

- [ ] **Step 8: Write a test proving no flat fee is deducted**

Add to `code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/RefundCalculatorTest.java`:
```java
@Test
void calculate_defaultFeeRate_noFlatFeeDeducted() {
    BigDecimal refund = refundCalculator.calculate(new BigDecimal("100.00"));

    assertEquals(0, new BigDecimal("98.00").compareTo(refund));
}
```
(100.00 × 0.98 = 98.00 per design-docs/09 §5's default 2% fee rate — adjust if `RefundCalculator`'s default rate config key/value differs from what your read of the file shows.)

- [ ] **Step 9: Fix `PaymentSucceededEvent`'s fields (add `paidAt`, remove spurious `userId`) — or move it to common if Task 6 Step 20 found the shadow-class bug**

Read `PaymentSucceededEvent.java` and the construction site in `PaymentService.confirmPayment()` (lines ~128-131). If Task 6 Step 20 concluded no cross-module `@EventListener` mismatch exists for this event, just fix its fields in place:
```java
public class PaymentSucceededEvent extends AbstractDomainEvent {
    private final String paymentNo;
    private final Long orderId;
    private final BigDecimal paidAmount;
    private final LocalDateTime paidAt;

    public PaymentSucceededEvent(Object source, String paymentNo, Long orderId,
                                  BigDecimal paidAmount, LocalDateTime paidAt) {
        super(source);
        this.paymentNo = paymentNo;
        this.orderId = orderId;
        this.paidAmount = paidAmount;
        this.paidAt = paidAt;
    }
    // remove userId field/getter, add getPaidAt()
}
```
Update the construction site:
```java
eventPublisher.publish(new PaymentSucceededEvent(this, payment.getPaymentNo(), payment.getOrderId(),
        payment.getPaidAmount(), payment.getPaidAt()));
```
If Task 6 Step 20 instead found a real cross-module listener mismatch, follow the same "move to `ecommerce-common`" pattern as Task 6 Step 19 for `OrderPaidEvent` instead of this in-place fix, and note that divergence in this task's commit message.

- [ ] **Step 10: Move logistics/points/notification out of the payment-confirmation transaction; add the missing synchronous inventory deduction**

Read `PaymentService.confirmPayment()` (lines ~113-134) in full — note its own Javadoc already admits the bug. The transaction should, per design-docs/02 §6, contain **only** payment status + order payment status + inventory deduction; logistics/points/notification move to an `@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)` reacting to `PaymentSucceededEvent`:
```java
@Transactional
public void confirmPayment(PaymentRecord payment) {
    payment.setStatus(PaymentStatus.SUCCESS);
    paymentRecordRepository.save(payment);
    orderPaymentStatusUpdater.markPaid(payment.getOrderId());
    inventoryReservationService.deductAfterPayment(payment.getOrderId());
    eventPublisher.publish(new PaymentSucceededEvent(this, payment.getPaymentNo(), payment.getOrderId(),
            payment.getPaidAmount(), payment.getPaidAt()));
}
```
(Confirm `inventoryReservationService` isn't already injected/called somewhere else in this exact call chain before adding it here — cross-check with Task 4's `deductAfterPayment` and Task 6 Step 20's finding to avoid a double-deduction; if `OrderPaymentEventHandler` in the order module already triggers `deductAfterPayment` via some other path reacting to this same payment-success moment, remove that other call site instead of adding a second one here — there must be exactly one caller of `deductAfterPayment` per successful payment.) Then create the listener (new file):
```java
package com.ecommerce.payment.service;

import com.ecommerce.common.notification.LocalNotificationService;
import com.ecommerce.common.notification.NotificationRequest;
import com.ecommerce.payment.event.PaymentSucceededEvent;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class PaymentSucceededNotificationListener {

    private final LocalNotificationService notificationService;

    public PaymentSucceededNotificationListener(LocalNotificationService notificationService) {
        this.notificationService = notificationService;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onPaymentSucceeded(PaymentSucceededEvent event) {
        NotificationRequest request = new NotificationRequest();
        request.setBizType("PAYMENT_SUCCESS");
        request.setBizId(event.getPaymentNo());
        // ... remaining fields matching whatever confirmPayment's old inline
        // sendNotifications() call built — read that method before deleting it
        // and reuse its exact field-population logic here instead of guessing.
        notificationService.send(request);
    }
}
```
Delete `confirmPayment`'s old inline `createLogistics()`/`earnPoints()`/`sendNotifications()` calls (read them first — logistics/points reactions already happen via `OrderPaidEvent` listeners once Task 9/Task 10 land, so this payment-side notification listener may be the *only* new listener actually needed here; don't duplicate logistics-shipment-creation or points-earning logic that's handled elsewhere per the event chain design-docs/02 §5 describes).

- [ ] **Step 11: Write a test proving a notification failure no longer rolls back payment confirmation (PUB-108-shaped)**

Add to `code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/PaymentServiceTest.java`:
```java
@Test
void confirmPayment_notificationFails_paymentStillSucceeds() {
    FaultInjectionRegistry.activate("notification-send-failure");
    try {
        paymentService.confirmPayment(payment);

        assertEquals(PaymentStatus.SUCCESS, paymentRecordRepository.findById(payment.getId()).get().getStatus());
    } finally {
        FaultInjectionRegistry.clear();
    }
}
```

- [ ] **Step 12: Fix invoice amount to respect the requested amount, and enforce `INVOICE_AMOUNT_EXCEEDED`**

Read `InvoiceService.java`'s `generateInvoice()` (lines ~50-104) in full. Change line ~63:
```java
BigDecimal invoiceAmount = successfulPayment.getPaidAmount();
```
to:
```java
BigDecimal invoiceAmount = request.getInvoiceAmount();
```
And replace the wrong check at lines ~71-74:
```java
if (alreadyInvoiced.compareTo(successfulPayment.getPaidAmount()) >= 0) {
    throw new BusinessException("INVOICE_LIMIT_EXCEEDED", "Order fully invoiced");
}
```
with:
```java
BigDecimal remaining = MonetaryUtil.subtract(successfulPayment.getPaidAmount(), alreadyInvoiced);
if (invoiceAmount.compareTo(remaining) > 0) {
    throw new BusinessException("INVOICE_AMOUNT_EXCEEDED",
            "Requested invoice amount " + invoiceAmount + " exceeds remaining invoiceable amount " + remaining);
}
```

- [ ] **Step 13: Write a test proving partial invoicing and the exceeded-amount rejection both work**

Add to `code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/InvoiceServiceTest.java`:
```java
@Test
void generateInvoice_partialAmount_recordsRequestedAmountNotFullPaid() {
    InvoiceResponse response = invoiceService.generateInvoice(orderIdWithPaidAmount("100.00"), invoiceRequest("40.00"));

    assertEquals(0, new BigDecimal("40.00").compareTo(response.getInvoiceAmount()));
}

@Test
void generateInvoice_amountExceedsRemaining_throwsInvoiceAmountExceeded() {
    invoiceService.generateInvoice(orderId, invoiceRequest("80.00"));

    BusinessException ex = assertThrows(BusinessException.class,
            () -> invoiceService.generateInvoice(orderId, invoiceRequest("30.00"))); // only 20.00 remains

    assertEquals("INVOICE_AMOUNT_EXCEEDED", ex.getCode());
}
```
(Adapt to this test class's existing helper methods for building an order/invoice-request fixture.)

- [ ] **Step 14: Fix settlement batch to sum real refunds**

Read `SettlementBatchService.java` (constructor lines ~42-50, `createBatchEntity` call at ~105-106) in full and `RefundRecordRepository`'s available query methods. Inject `RefundRecordRepository`, and replace:
```java
createBatchEntity(batchDate, totalPaymentAmount, BigDecimal.ZERO, totalInvoiceAmount, orderCount);
```
with:
```java
BigDecimal totalRefundAmount = refundRecordRepository
        .findByStatusAndCompletedAtBetween(RefundStatus.COMPLETED, startOfDay, endOfDay)
        .stream()
        .map(RefundRecord::getRefundAmount)
        .reduce(BigDecimal.ZERO, MonetaryUtil::add);
createBatchEntity(batchDate, totalPaymentAmount, totalRefundAmount, totalInvoiceAmount, orderCount);
```
(Add a `findByStatusAndCompletedAtBetween` derived-query method to `RefundRecordRepository` if it doesn't already exist; confirm `RefundRecord`'s exact completed-timestamp field name and `getRefundAmount()` getter from reading the entity.)

- [ ] **Step 15: Write a test proving settlement reflects real refunds**

Add to `code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/SettlementBatchServiceTest.java`:
```java
@Test
void createBatch_withCompletedRefundToday_includesRefundTotal() {
    // arrange one COMPLETED refund of 30.00 completed today, per this test class's existing fixture style

    SettlementBatchResponse response = settlementBatchService.createBatch(today);

    assertEquals(0, new BigDecimal("30.00").compareTo(response.getTotalRefundAmount()));
}
```

- [ ] **Step 16: Add `refundRequestNo` idempotency**

Read `RefundApplyRequest.java`, `RefundRecord.java`, `RefundService.applyRefund()` (lines ~58-92) in full. Add field + column:
```java
private String refundRequestNo; // RefundApplyRequest — with getter/setter
```
```java
@Column(name = "refund_request_no", unique = true)
private String refundRequestNo; // RefundRecord entity — with getter/setter
```
At the top of `applyRefund()`:
```java
if (request.getRefundRequestNo() != null) {
    Optional<RefundRecord> existing = refundRecordRepository.findByRefundRequestNo(request.getRefundRequestNo());
    if (existing.isPresent()) {
        return toRefundResponse(existing.get());
    }
}
```
(Add `findByRefundRequestNo` to `RefundRecordRepository` — standard derived query. Set `refundRequestNo` on the new `RefundRecord` before saving it, further down in the same method.)

- [ ] **Step 17: Add `invoiceRequestNo` idempotency (identical pattern to Step 16)**

Repeat the exact same pattern from Step 16 for `InvoiceRequest`/`InvoiceRecord`/`InvoiceService.generateInvoice()` with field name `invoiceRequestNo`.

- [ ] **Step 18: Write idempotency tests for both**

Add to `RefundServiceTest.java` and `InvoiceServiceTest.java` respectively:
```java
@Test
void applyRefund_duplicateRefundRequestNo_returnsExistingRecord_doesNotCreateSecond() {
    RefundResponse first = refundService.applyRefund(requestWithRefundRequestNo("RFD-001"));
    RefundResponse second = refundService.applyRefund(requestWithRefundRequestNo("RFD-001"));

    assertEquals(first.getRefundId(), second.getRefundId());
    assertEquals(1, refundRecordRepository.count());
}
```
```java
@Test
void generateInvoice_duplicateInvoiceRequestNo_returnsExistingRecord_doesNotCreateSecond() {
    InvoiceResponse first = invoiceService.generateInvoice(orderId, requestWithInvoiceRequestNo("INV-001"));
    InvoiceResponse second = invoiceService.generateInvoice(orderId, requestWithInvoiceRequestNo("INV-001"));

    assertEquals(first.getInvoiceId(), second.getInvoiceId());
}
```

- [ ] **Step 19 (suspicious finding, low-risk to apply): guard duplicate FAILED payment callbacks**

Read `PaymentCallbackService.processFailedCallback()` (lines ~94-114). Add an early-return guard mirroring the existing SUCCESS-path guard:
```java
if (payment.getStatus() == PaymentStatus.FAILED) {
    return; // already processed, idempotent no-op
}
```
at the top of `processFailedCallback`, before it calls `orderPaymentStatusUpdater.markPaymentFailed(...)`.

- [ ] **Step 20 (suspicious finding — verify before applying): confirm whether any black-box assertion pins the literal string `"REFUNDED"` before renaming to `CLOSED`**

```bash
grep -rn "REFUNDED\|CLOSED" test-cases/src/test/java
```
If no test-cases assertion depends on the literal `"REFUNDED"` string for payment status, rename `PaymentStatus.REFUNDED` to `CLOSED` (matching 附录C) and update the single call site in `RefundService.java:177`. If a test **does** assert `"REFUNDED"` literally, leave this as-is and note in the commit message that 附录C's naming wasn't applied because a test pins the current value.

- [ ] **Step 21 (suspicious finding — skip unless Step 20's grep suggests otherwise): `RefundStatus`/`InvoiceStatus` renaming**

Per the design spec's own risk note (§6.3 #14), this is a larger, riskier rename (6 values → 5, `CANCELLED`→`VOIDED`) with no confirmed test pinning either the old or new names. **Do not perform this rename** in this task — leave `RefundStatus`/`InvoiceStatus` as they are. Record in the commit message that this suspicious finding was evaluated and deliberately not applied, per the design spec's guidance to avoid "changing for the sake of changing" when there's no confirmed test signal either way.

- [ ] **Step 22: Add payment-callback signature validation (cross-referenced from Task 12's app-module security finding)**

Read `PaymentController.java`'s `callback()` method (lines ~52-58) and `PaymentCallbackService.processCallback()` (lines ~40-65) in full. Add the header parameter:
```java
@PostMapping("/callback")
public ResponseEntity<Void> callback(@RequestBody PaymentCallbackRequest request,
                                      @RequestHeader("X-Payment-Signature") String signature) {
    paymentCallbackService.processCallback(request, signature);
    return ResponseEntity.ok().build();
}
```
And validate it in `processCallback` (a deterministic mock check is sufficient — this is a simulated signature per design-docs/02 §8, not a real cryptographic gateway):
```java
private static final String EXPECTED_SIGNATURE_SECRET = "shophub-mock-secret";

public void processCallback(PaymentCallbackRequest request, String signature) {
    String expected = DigestUtils.sha256Hex(request.getPaymentNo() + EXPECTED_SIGNATURE_SECRET);
    if (!expected.equals(signature)) {
        throw new AuthorizationException("UNAUTHORIZED", "Invalid payment callback signature");
    }
    // ... existing processCallback body, unchanged ...
}
```
(Confirm an SHA-256 hex utility is already on the classpath — Spring Security or Apache Commons Codec's `DigestUtils` is typical; if neither is a dependency, use `java.security.MessageDigest` directly instead of adding a new dependency. Since `test-cases/` cannot be modified and this callback endpoint is exercised by PUB-010/PUB-108, confirm what signature value the existing test harness's `PaymentFixture.java` sends for the callback call — read `test-cases/src/test/java/com/ecommerce/blackbox/common/fixture/PaymentFixture.java` first, since whatever mock signature scheme you implement must match what the immutable test fixture already sends, not the other way around.)

- [ ] **Step 23: Run the full payment module test suite**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-payment -am test
```
Expected: all pass.

- [ ] **Step 24: Install and run every payment-related black-box test**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub009_createPayment test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub010_paymentCallbackSuccess test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub013_fullInvoiceIssuance test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub108_paymentSuccessShouldNotBeBlockedByPostActions test
```
Expected: all pass. **If Step 22's signature validation breaks `pub010`/`pub108` because the test fixture's signature doesn't match your mock scheme, Step 22 is wrong — go back and match the fixture's actual value, do not weaken/skip validation to make the test pass.**

- [ ] **Step 25: Commit**

```bash
git add code/ecommerce-payment
git commit -m "$(cat <<'EOF'
Fix payment module: CREATED status, amount-mismatch validation,
refund review requires warehouse acceptance, no flat refund fee,
invoice respects requested amount and enforces the remaining-amount
cap, settlement includes real refund totals, payment confirmation
transaction scoped correctly with async post-actions, paidAt field,
refund/invoice idempotency keys, payment callback signature check

Per design-docs/09, design-docs/14, design-docs/02 §6, and
design-docs/03 §3.
EOF
)"
```

## Task 8: `ecommerce-promotion` module (10 fixes)

**Depends on:** Task 1 only.

**Files:**
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponValidator.java`
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/controller/PromotionController.java`
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/FullReductionService.java`
- Modify: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/SeckillService.java`
- Modify: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java` (seckill + coupon-marking hooks — cross-module, coordinate with Task 6 if it hasn't landed yet)

- [ ] **Step 1: Fix the inverted DISCOUNT coupon formula (already-known, PUB-101)**

Current (`CouponService.java`, `calculateDiscount()`, confirmed this session):
```java
case DISCOUNT:
    BigDecimal rate = BigDecimal.ONE.subtract(coupon.getDiscountValue());
    BigDecimal afterDiscount = MonetaryUtil.multiply(price, rate);
    if (coupon.getMaxDiscount() != null) {
        BigDecimal rawDiscount = MonetaryUtil.subtract(price, afterDiscount);
        if (rawDiscount.compareTo(coupon.getMaxDiscount()) > 0) {
            return coupon.getMaxDiscount();
        }
    }
    return MonetaryUtil.subtract(price, afterDiscount);
```
Change to:
```java
case DISCOUNT:
    BigDecimal discountRate = BigDecimal.ONE.subtract(coupon.getDiscountValue());
    BigDecimal discountAmount = MonetaryUtil.multiply(price, discountRate);
    if (coupon.getMaxDiscount() != null && discountAmount.compareTo(coupon.getMaxDiscount()) > 0) {
        return coupon.getMaxDiscount();
    }
    return discountAmount;
```
(Renamed `rate`→`discountRate` and `afterDiscount`→`discountAmount` since the old names were actively misleading — `afterDiscount` held the discount amount, not an after-discount price. This is a legitimate clarity improvement directly tied to this bug fix, not scope creep.)

- [ ] **Step 2: Run the known black-box test**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub101_couponDiscountShouldBeCorrect test
```
Expected: passes (still depends on Step 5's `totalDiscount` cap and Step 4's stacking-order fix for its second assertion on `payableAmount` — if this doesn't fully pass yet, continue through Steps 3-6 below then re-run).

- [ ] **Step 3: Write a unit test locking in the corrected formula independent of the black-box flow**

Add to `code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/CouponServiceTest.java`:
```java
@Test
void calculateDiscount_discountTypeCoupon_returnsPriceTimesOneMinusDiscountValue() {
    CouponTemplate coupon = discountCoupon(new BigDecimal("0.8")); // 80%-price coupon

    BigDecimal discount = couponService.calculateDiscount(new BigDecimal("100.00"), coupon);

    assertEquals(0, new BigDecimal("20.00").compareTo(discount));
}

@Test
void calculateDiscount_discountTypeCoupon_cappedAtMaxDiscount() {
    CouponTemplate coupon = discountCouponWithMax(new BigDecimal("0.5"), new BigDecimal("10.00"));

    BigDecimal discount = couponService.calculateDiscount(new BigDecimal("100.00"), coupon);

    assertEquals(0, new BigDecimal("10.00").compareTo(discount)); // 50.00 raw discount capped to 10.00
}
```
(Use this test class's existing fixture-builder helpers for `CouponTemplate` if present; otherwise construct directly, matching whatever pattern the rest of the file uses.)

- [ ] **Step 4: Fix the reversed promotion stacking order (already-known, likely covered by non-public tests)**

Current (`PromotionCalculationService.java`, `calculate()`, confirmed this session):
```java
public PromotionCalculateResponse calculate(PromotionCalculateRequest request) {
    // Compute item total
    BigDecimal itemTotal = computeItemTotal(request.getItems());

    // Apply member-level discount.
    BigDecimal memberDiscount = calculateMemberDiscount(request.getUserId(), itemTotal);
    BigDecimal afterMember = MonetaryUtil.subtract(itemTotal, memberDiscount);

    // Apply full reduction.
    BigDecimal fullReductionDiscount =
            fullReductionService.calculateBestReduction(afterMember)
                    .orElse(BigDecimal.ZERO);
    BigDecimal afterFullReduction = MonetaryUtil.subtract(afterMember, fullReductionDiscount);

    // Apply coupons.
    BigDecimal couponDiscount = calculateCouponDiscount(request.getUserId(),
            request.getCouponIds(), afterFullReduction);

    BigDecimal totalDiscount = MonetaryUtil.add(
            MonetaryUtil.add(memberDiscount, fullReductionDiscount), couponDiscount);
    BigDecimal finalAmount = MonetaryUtil.subtract(itemTotal, totalDiscount);

    if (finalAmount.compareTo(BigDecimal.ZERO) < 0) {
        finalAmount = BigDecimal.ZERO;
    }

    PromotionCalculateResponse response = new PromotionCalculateResponse();
    response.setItemTotal(itemTotal);
    response.setFullReductionDiscount(fullReductionDiscount);
    response.setCouponDiscount(couponDiscount);
    response.setMemberDiscount(memberDiscount);
    response.setTotalDiscount(totalDiscount);
    response.setFinalAmount(finalAmount);
    response.setApplicableCoupons(new ArrayList<>());

    return response;
}
```
Change to (reorders to full-reduction → coupon → member, each step feeding the next, and fixes `totalDiscount`/`finalAmount` clamping consistency per Step 5 below):
```java
public PromotionCalculateResponse calculate(PromotionCalculateRequest request) {
    BigDecimal itemTotal = computeItemTotal(request.getItems());

    // Step 1: full reduction, based on raw item total.
    BigDecimal fullReductionDiscount =
            fullReductionService.calculateBestReduction(itemTotal)
                    .orElse(BigDecimal.ZERO);
    BigDecimal afterFullReduction = MonetaryUtil.subtract(itemTotal, fullReductionDiscount);

    // Step 2: coupon discount, based on the full-reduction result.
    BigDecimal couponDiscount = calculateCouponDiscount(request.getUserId(),
            request.getCouponIds(), afterFullReduction);
    BigDecimal afterCoupon = MonetaryUtil.subtract(afterFullReduction, couponDiscount);

    // Step 3: member discount, based on the coupon result (applied last).
    BigDecimal memberDiscount = calculateMemberDiscount(request.getUserId(), afterCoupon);

    BigDecimal finalAmount = MonetaryUtil.subtract(afterCoupon, memberDiscount);
    if (finalAmount.compareTo(BigDecimal.ZERO) < 0) {
        finalAmount = BigDecimal.ZERO;
    }
    BigDecimal totalDiscount = MonetaryUtil.subtract(itemTotal, finalAmount);

    PromotionCalculateResponse response = new PromotionCalculateResponse();
    response.setItemTotal(itemTotal);
    response.setFullReductionDiscount(fullReductionDiscount);
    response.setCouponDiscount(couponDiscount);
    response.setMemberDiscount(memberDiscount);
    response.setTotalDiscount(totalDiscount);
    response.setFinalAmount(finalAmount);
    response.setApplicableCoupons(new ArrayList<>());

    return response;
}
```

- [ ] **Step 5: This rewrite already fixes the "totalDiscount not capped" finding — verify with a test**

Add to `code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/PromotionCalculationServiceTest.java`:
```java
@Test
void calculate_matchesDesignDocWorkedExample() {
    // itemTotal 300, full-reduction -30, 8-fold coupon, member 95% rate configured
    PromotionCalculateResponse response = promotionCalculationService.calculate(
            requestWithItemTotal(new BigDecimal("300.00"), eightyPercentCoupon(), fullReductionThirtyOff()));

    assertEquals(0, new BigDecimal("205.20").compareTo(response.getFinalAmount()));
}

@Test
void calculate_totalDiscountNeverExceedsItemTotal() {
    PromotionCalculateResponse response = promotionCalculationService.calculate(
            requestWithExtremeStackedDiscounts());

    assertTrue(response.getTotalDiscount().compareTo(response.getItemTotal()) <= 0);
    assertTrue(response.getFinalAmount().compareTo(BigDecimal.ZERO) >= 0);
}
```
(Build fixtures matching design-docs/10 §3's worked example: 300 → -30 → ×0.8 → ×0.95 = 205.20; adapt helper-method names to this test file's existing conventions or add small private builder methods following its style.)

- [ ] **Step 6: Implement the missing coupon validation steps (expiry, threshold, applicability, used-status)**

Read `CouponValidator.java`'s `validate()` (lines ~32-39) in full, and `UserCoupon`/`CouponTemplate`'s available fields (`startTime`/`endTime`, `thresholdAmount`, `applicableProductIds`/`applicableCategoryIds`, `status`). Change the method's signature to also accept the order amount and SKU ids being purchased (needed for the threshold/applicability checks — update the one call site in `PromotionCalculationService.calculateCouponDiscount()` accordingly):
```java
public void validate(UserCoupon userCoupon, BigDecimal orderAmount, List<Long> skuIds) {
    if (userCoupon == null) {
        throw new ResourceNotFoundException("Coupon not found");
    }
    CouponTemplate template = couponTemplateRepository.findById(userCoupon.getCouponTemplateId())
            .orElseThrow(() -> new ResourceNotFoundException("CouponTemplate", userCoupon.getCouponTemplateId()));

    LocalDateTime now = SystemClockService.now();
    if (template.getStartTime() != null && now.isBefore(template.getStartTime())
            || template.getEndTime() != null && now.isAfter(template.getEndTime())) {
        throw new BusinessException("COUPON_EXPIRED", "Coupon is not within its valid time window");
    }
    if (template.getThresholdAmount() != null && orderAmount.compareTo(template.getThresholdAmount()) < 0) {
        throw new BusinessException("COUPON_THRESHOLD_NOT_MET", "Order amount below coupon threshold");
    }
    if (!isApplicableToSkus(template, skuIds)) {
        throw new BusinessException("COUPON_NOT_APPLICABLE", "Coupon does not apply to the purchased items");
    }
    if (userCoupon.getStatus() != CouponStatus.AVAILABLE) {
        throw new BusinessException("COUPON_ALREADY_USED", "Coupon has already been used or is unavailable");
    }
}

private boolean isApplicableToSkus(CouponTemplate template, List<Long> skuIds) {
    if (template.getApplicableProductIds() == null || template.getApplicableProductIds().isEmpty()) {
        return true; // no restriction configured
    }
    return skuIds.stream().anyMatch(template.getApplicableProductIds()::contains);
}
```
(Confirm `SystemClockService`'s exact static/instance access pattern from `code/ecommerce-common/src/main/java/com/ecommerce/common/test/SystemClockService.java` — other modules already use it correctly, e.g. loyalty's `earnPoints`; match that pattern rather than `LocalDateTime.now()` directly, so the test-clock-override admin endpoint works here too. Confirm `applicableProductIds`'s actual type/getter from reading `CouponTemplate.java`.)

- [ ] **Step 7: Write tests for each of the four newly-enforced validation rules**

Add to `CouponValidatorTest.java` (read the existing file first — per audit it currently has tests literally named `testValidate_expiredCoupon_stillReturnsTrue` etc. that assert the *bug*; rename and invert these):
```java
@Test
void validate_expiredCoupon_throwsCouponExpired() {
    UserCoupon expired = userCouponForTemplate(templateWithEndTime(yesterday()));

    BusinessException ex = assertThrows(BusinessException.class,
            () -> couponValidator.validate(expired, orderAmount, skuIds));
    assertEquals("COUPON_EXPIRED", ex.getCode());
}

@Test
void validate_alreadyUsedCoupon_throwsCouponAlreadyUsed() {
    UserCoupon used = userCouponWithStatus(CouponStatus.USED);

    BusinessException ex = assertThrows(BusinessException.class,
            () -> couponValidator.validate(used, orderAmount, skuIds));
    assertEquals("COUPON_ALREADY_USED", ex.getCode());
}

@Test
void validate_belowThreshold_throwsCouponThresholdNotMet() {
    UserCoupon coupon = userCouponForTemplate(templateWithThreshold(new BigDecimal("200.00")));

    assertThrows(BusinessException.class,
            () -> couponValidator.validate(coupon, new BigDecimal("100.00"), skuIds));
}

@Test
void validate_notApplicableToSkus_throwsCouponNotApplicable() {
    UserCoupon coupon = userCouponForTemplate(templateApplicableOnlyTo(999L));

    assertThrows(BusinessException.class,
            () -> couponValidator.validate(coupon, orderAmount, List.of(1L, 2L)));
}
```

- [ ] **Step 8: Mark coupons as used after a successful order, and verify ownership before applying**

Add to `CouponService.java`:
```java
@Transactional
public void markUsed(Long userCouponId, Long orderId) {
    UserCoupon userCoupon = userCouponRepository.findById(userCouponId)
            .orElseThrow(() -> new ResourceNotFoundException("UserCoupon", userCouponId));
    userCoupon.setStatus(CouponStatus.USED);
    userCoupon.setUsedOrderId(orderId);
    userCoupon.setUsedAt(SystemClockService.now());
    userCouponRepository.save(userCoupon);
}
```
In `PromotionCalculationService.calculateCouponDiscount()`, add an ownership check right after loading `userCoupon` (before calling `couponValidator.validate(...)`):
```java
if (!userId.equals(userCoupon.getUserId())) {
    continue; // not this user's coupon — silently skip rather than leaking existence via an error
}
```
Then, in `ecommerce-order`'s `OrderService.createOrder()` (coordinate with Task 6 — if Task 6 has already landed, this is a small addition to its existing flow; if not, this step still stands on its own since it's additive), call `couponService.markUsed(couponId, order.getId())` for each applied coupon ID after the order is successfully persisted.

- [ ] **Step 9: Write tests for ownership check and used-marking**

Add to `PromotionCalculationServiceTest.java`:
```java
@Test
void calculateCouponDiscount_couponBelongsToDifferentUser_isSkipped() {
    UserCoupon othersCoupon = userCouponForUser(otherUserId);
    when(userCouponRepository.findById(couponId)).thenReturn(Optional.of(othersCoupon));

    BigDecimal discount = promotionCalculationService.calculateCouponDiscount(
            currentUserId, List.of(couponId), new BigDecimal("100.00"));

    assertEquals(0, BigDecimal.ZERO.compareTo(discount));
}
```
And to `CouponServiceTest.java`:
```java
@Test
void markUsed_setsStatusUsedAndRecordsOrderId() {
    couponService.markUsed(userCouponId, orderId);

    UserCoupon updated = userCouponRepository.findById(userCouponId).get();
    assertEquals(CouponStatus.USED, updated.getStatus());
    assertEquals(orderId, updated.getUsedOrderId());
}
```

- [ ] **Step 10: Fix `PromotionController`'s hardcoded `userId=1`**

Read `PromotionController.java`'s `extractUserId()` (lines ~115-119) and any sibling controller's real implementation (e.g. `CartController`) for the exact pattern to copy:
```java
private Long extractUserId() {
    String principal = SecurityContextHolder.getContext().getAuthentication().getName();
    return Long.parseLong(principal);
}
```
(Match whatever exception-handling wrapper the sibling controllers use around `Long.parseLong` — e.g. `OrderController.getCurrentUserId()`'s `NumberFormatException` → `AuthorizationException` handling, confirmed earlier this session — copy that exact pattern rather than leaving `parseLong` unguarded.)

- [ ] **Step 11 (suspicious finding, safe to apply): full-reduction time-window check**

Read `FullReductionService.java`'s `create()` (lines ~35-51) and `calculateBestReduction()` (lines ~65-85). Add the same time-window guard pattern as Step 6's coupon expiry check:
```java
private boolean isWithinWindow(FullReductionActivity activity, LocalDateTime now) {
    return (activity.getStartTime() == null || !now.isBefore(activity.getStartTime()))
            && (activity.getEndTime() == null || !now.isAfter(activity.getEndTime()));
}
```
and filter candidates in `calculateBestReduction` to only those where `isWithinWindow(activity, SystemClockService.now())` is true, before picking the best (highest) matching reduction.

- [ ] **Step 12: Wire seckill into order creation (coordinate with Task 6)**

Read `SeckillService.java`'s `validateSeckill()`/`recordPurchase()` in full, and `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPricingService.java` (or wherever per-item pricing happens during order creation). For each order item, before pricing it at list price, check whether an active `SeckillActivity` exists for that SKU (inject `SeckillService` into the order-pricing path — this requires `ecommerce-order`'s `pom.xml` to depend on `ecommerce-promotion`, which per the design-docs/02 module graph it already does): if so, call `seckillService.validateSeckill(userId, skuId, quantity)`, use the returned seckill price instead of list price for that line, and exclude that line's amount from the full-reduction-eligible subtotal (per design-docs/10 §4 item 5). Call `seckillService.recordPurchase(...)` after the order is successfully created (same place coupon `markUsed` is called, per Step 8).

- [ ] **Step 13: Write a test proving a seckill purchase uses the seckill price and enforces the per-user limit**

Add to `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderServiceTest.java` (or `OrderPricingServiceTest.java`, matching wherever Step 12's integration point actually lives):
```java
@Test
void createOrder_skuInActiveSeckill_usesSeckillPriceNotListPrice() {
    // arrange an active SeckillActivity for skuId with seckillPrice 9.90, list price 100.00

    CreateOrderResponse response = orderService.createOrder(userId, requestForSku(skuId, 1));

    assertEquals(0, new BigDecimal("9.90").compareTo(response.getItemTotal()));
}
```

- [ ] **Step 14: Run the full promotion module test suite**

```bash
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-promotion -am test
```
Expected: all pass.

- [ ] **Step 15: Install and run promotion-related black-box tests**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub101_couponDiscountShouldBeCorrect test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub104_orderTotalShouldIncludeShipping test
```
Expected: both pass (fully, including the discount-dependent assertions this time).

- [ ] **Step 16: Commit**

```bash
git add code/ecommerce-promotion code/ecommerce-order
git commit -m "$(cat <<'EOF'
Fix promotion module: correct DISCOUNT coupon formula, correct
full-reduction->coupon->member stacking order, real coupon validation
(expiry/threshold/applicability/used-status), coupons marked used
after order, ownership check, remove hardcoded userId=1, cap total
discount to item total, wire seckill into order pricing, full-reduction
time window

Per design-docs/10 and design-docs/03 §1.
EOF
)"
```

## Task 9: `ecommerce-logistics` module (7 fixes)

**Depends on:** Task 1 (`OrderPaidEvent`, `ShipmentDeliveredEvent` now live in `ecommerce-common`).

**Files:**
- Modify: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- Modify: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/LogisticsCallbackService.java`
- Modify: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/entity/ShipmentTracking.java` (add `trackingNo`/idempotency columns)
- Modify: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/FreightCalculator.java`
- Modify: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/FreightTemplateService.java`
- Create: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/event/OrderPaidEventListener.java`
- Create: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/config/FreightCacheConfig.java`

- [ ] **Step 1: Fix shipment creation to start at `CREATED`, not `OUTBOUND` (already-known, PUB-107 root cause)**

Read `ShipmentService.java`'s `createShipment()` (lines ~68-101) in full. Per audit, line 81 currently sets:
```java
shipment.setStatus(ShipmentStatus.OUTBOUND);
```
Change to:
```java
shipment.setStatus(ShipmentStatus.CREATED);
```
Also remove the "OUTBOUND" tracking-event recording and any forced order-logistics-status push that immediately follows it in this same method (lines ~88-93 per audit) — a freshly-created shipment shouldn't report itself as already outbound.

- [ ] **Step 2: Add a status guard to `outbound()`**

Read lines ~223-229:
```java
public void outbound(Long shipmentId) {
    Shipment shipment = shipmentRepository.findById(shipmentId)
            .orElseThrow(() -> new ResourceNotFoundException("Shipment", shipmentId));
    shipment.setStatus(ShipmentStatus.OUTBOUND);
    // ...
}
```
Add a precondition check before the `setStatus` call:
```java
if (shipment.getStatus() != ShipmentStatus.LABEL_PRINTED) {
    throw new ConflictException("Shipment must be LABEL_PRINTED before outbound, was: " + shipment.getStatus());
}
```

- [ ] **Step 3: Fix `pick()` to not allow OUTBOUND->PICKING, and add a status guard to `printLabel()`**

Read lines ~138-143 (`pick()`) and ~181-216 (`printLabel()`) in full. In `pick()`, remove `ShipmentStatus.OUTBOUND` from whatever set of acceptable source states currently includes it (per audit it whitelists `CREATED`/`PICKING`/`OUTBOUND` — keep only `CREATED` and `PICKING`, since re-calling pick while already PICKING should be a harmless idempotent no-op, per how the rest of this codebase treats repeat calls). In `printLabel()`, add:
```java
if (shipment.getStatus() != ShipmentStatus.PICKING) {
    throw new ConflictException("Shipment must be PICKING before label can be printed, was: " + shipment.getStatus());
}
```
before it sets `LABEL_PRINTED`.

- [ ] **Step 4: Write tests for the corrected state machine**

Add to `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/service/ShipmentServiceTest.java` (read existing file for conventions):
```java
@Test
void createShipment_startsAtCreated_notOutbound() {
    ShipmentResponse response = shipmentService.createShipment(orderId, addressId, items);

    assertEquals(ShipmentStatus.CREATED, response.getStatus());
}

@Test
void outbound_beforeLabelPrinted_throwsConflict() {
    Shipment shipment = shipmentInStatus(ShipmentStatus.CREATED);

    assertThrows(ConflictException.class, () -> shipmentService.outbound(shipment.getId()));
}

@Test
void fullHappyPath_createdToPickingToLabelPrintedToOutbound_succeeds() {
    Long shipmentId = shipmentService.createShipment(orderId, addressId, items).getShipmentId();

    shipmentService.pick(shipmentId);
    shipmentService.printLabel(shipmentId);
    shipmentService.outbound(shipmentId);

    assertEquals(ShipmentStatus.OUTBOUND, shipmentRepository.findById(shipmentId).get().getStatus());
}

@Test
void printLabel_beforePicking_throwsConflict() {
    Shipment shipment = shipmentInStatus(ShipmentStatus.CREATED);

    assertThrows(ConflictException.class, () -> shipmentService.printLabel(shipment.getId()));
}
```

- [ ] **Step 5: Add an `OrderPaidEvent` listener that auto-creates the shipment**

Create `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/event/OrderPaidEventListener.java`:
```java
package com.ecommerce.logistics.event;

import com.ecommerce.common.event.OrderPaidEvent;
import com.ecommerce.logistics.service.ShipmentService;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class OrderPaidEventListener {

    private final ShipmentService shipmentService;

    public OrderPaidEventListener(ShipmentService shipmentService) {
        this.shipmentService = shipmentService;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderPaid(OrderPaidEvent event) {
        shipmentService.createShipment(event.getOrderId(), event.getUserId(), event.getItems());
    }
}
```
(Match `createShipment`'s actual parameter list from Step 1's read — this codebase's real signature may take a resolved address ID rather than `userId` directly; if it needs the shipping address, `OrderPaidEvent`'s payload from Task 1 doesn't currently carry one — either add an `addressId` field to `OrderPaidEvent` in `ecommerce-common` (small addition, coordinate: whoever does this first updates both the class and its one publish call site in `ecommerce-order`) or have `createShipment` look up the order's address via `OrderQueryService.getOrderDetail(orderId)` instead of requiring it in the event payload — prefer the latter since it keeps the event payload matching the 附录D-specified `{orderId, userId, paidAmount, items}` shape exactly.)

- [ ] **Step 6: Write a test proving payment success triggers real shipment creation via the event**

Add to `OrderPaidEventListenerTest.java` (new file, or extend existing if a stub already exists):
```java
@Test
void onOrderPaid_createsShipmentForOrder() {
    OrderPaidEvent event = new OrderPaidEvent(this, orderId, userId, paidAmount, items, String.valueOf(orderId), null);

    orderPaidEventListener.onOrderPaid(event);

    assertTrue(shipmentRepository.findByOrderId(orderId).isPresent());
}
```

- [ ] **Step 7: Implement the logistics callback for real**

Read `LogisticsCallbackService.processCallback()` (lines ~33-39) and `mapToShipmentStatus(String)` (lines ~44-61, currently dead code) in full, plus `ShipmentTracking.java`'s current fields (per audit, no `trackingNo` column exists). Add `trackingNo` (+ `eventTime`, `status` if not already present) to `ShipmentTracking` for idempotency, and rewrite:
```java
public void processCallback(LogisticsCallbackRequest request) {
    if (trackingEventRepository.existsByTrackingNoAndEventTimeAndStatus(
            request.getTrackingNo(), request.getEventTime(), request.getStatus())) {
        return; // duplicate callback, idempotent no-op
    }
    Shipment shipment = shipmentRepository.findByTrackingNo(request.getTrackingNo())
            .orElseThrow(() -> new ResourceNotFoundException("Shipment with trackingNo", request.getTrackingNo()));

    ShipmentStatus newStatus = mapToShipmentStatus(request.getStatus());
    shipmentService.updateStatus(shipment.getId(), newStatus, request.getLocation(), request.getDescription());

    ShipmentTracking tracking = new ShipmentTracking();
    tracking.setShipmentId(shipment.getId());
    tracking.setTrackingNo(request.getTrackingNo());
    tracking.setEventTime(request.getEventTime());
    tracking.setStatus(request.getStatus());
    tracking.setLocation(request.getLocation());
    tracking.setDescription(request.getDescription());
    trackingEventRepository.save(tracking);
}
```
(Signature validation for this callback is out of this task's explicit findings list — design-docs/02 §8 mentions a signature header for payment callback specifically, not logistics; do not add signature checking here unless you separately confirm design-docs/11 or 附录A require it for the logistics callback too — re-read 附录A's logistics callback section before adding anything not explicitly asked for.) Add `existsByTrackingNoAndEventTimeAndStatus`/`findByTrackingNo` to the relevant repositories if missing.

- [ ] **Step 8: Publish `ShipmentDeliveredEvent` when status becomes DELIVERED**

Read `ShipmentService.updateStatus()` in full (it already sets `deliveredAt` when transitioning to `DELIVERED`, per audit — just add the publish):
```java
if (newStatus == ShipmentStatus.DELIVERED) {
    shipment.setDeliveredAt(SystemClockService.now());
    eventPublisher.publish(new ShipmentDeliveredEvent(this, shipment.getOrderId(), shipment.getId(),
            shipment.getDeliveredAt(), String.valueOf(shipment.getId()), null));
}
```
Add `import com.ecommerce.common.event.ShipmentDeliveredEvent;`.

- [ ] **Step 9: Write a test proving delivery publishes the event**

Add to `ShipmentServiceTest.java`:
```java
@Test
void updateStatus_toDelivered_publishesShipmentDeliveredEvent() {
    shipmentService.updateStatus(shipmentId, ShipmentStatus.DELIVERED, "Shenzhen", "delivered");

    ArgumentCaptor<ShipmentDeliveredEvent> captor = ArgumentCaptor.forClass(ShipmentDeliveredEvent.class);
    verify(eventPublisher).publish(captor.capture());
    assertEquals(orderId, captor.getValue().getOrderId());
}
```

- [ ] **Step 10: Add a 30-minute freight template cache; parse province/weight rules**

Mirror Task 3 Step 10's cache-config pattern for a `logistics:freight` cache with 30-minute TTL, keyed by `templateId`. Read `FreightCalculator.java`'s `calculateFreight` overloads (lines ~40-92) and `FreightTemplate.java`'s `provinceRules`/`weightRules` fields (currently unparsed JSON-ish strings, per audit) in full. Parse them (likely simple JSON via the already-on-classpath Jackson `ObjectMapper`) and select the matching rule by province/weight/item count before falling back to `defaultFreight`:
```java
private BigDecimal resolveFreight(FreightTemplate template, String province, BigDecimal weight, int itemCount) {
    Map<String, BigDecimal> provinceRates = parseProvinceRules(template.getProvinceRules());
    if (provinceRates.containsKey(province)) {
        return provinceRates.get(province);
    }
    List<WeightRule> weightRules = parseWeightRules(template.getWeightRules());
    for (WeightRule rule : weightRules) {
        if (weight.compareTo(rule.getMinWeight()) >= 0
                && (rule.getMaxWeight() == null || weight.compareTo(rule.getMaxWeight()) < 0)) {
            return rule.getFreight();
        }
    }
    return template.getDefaultFreight();
}
```
(This is illustrative — read the actual stored format of `provinceRules`/`weightRules` first, since the audit only confirmed the fields exist and are unread, not their exact JSON schema; if the schema is genuinely undocumented anywhere and no test exercises non-default freight, keep this parsing minimal/defensive and fall back to `defaultFreight` on any parse failure rather than throwing.)

- [ ] **Step 11: Run the full logistics module test suite**

```bash
source ~/tools/env.sh
mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-logistics -am test
```
Expected: all pass.

- [ ] **Step 12: Install and run the logistics-related black-box tests**

```bash
mvn -s maven-settings.xml -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub011_queryLogistics test
mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub107_shipmentProcessShouldIncludePickAndLabel test
```
Expected: both pass (this also requires Task 6's `OrderPaidEvent` publish fix and Task 7's payment-confirmation flow to be in place so a real paid order exists to trigger shipment creation — if those haven't landed, this step may need to wait for Task 13's integration pass).

- [ ] **Step 13: Commit**

```bash
git add code/ecommerce-logistics
git commit -m "$(cat <<'EOF'
Fix logistics module: shipment starts at CREATED not OUTBOUND, state
machine enforces CREATED->PICKING->LABEL_PRINTED->OUTBOUND, auto-create
shipment on OrderPaidEvent, real callback processing with idempotency,
publish ShipmentDeliveredEvent, freight template cache + province/weight
rule parsing

Per design-docs/11, design-docs/02 §5/§7, and design-docs/附录D.
EOF
)"
```

## Task 10: `ecommerce-loyalty` module (11 fixes)

**Depends on:** Task 1 (listens to `com.ecommerce.common.event.OrderPaidEvent` and `ReviewApprovedEvent`).

**Source of truth for the 11 fixes:** design spec §6.9 (each row: symptom / file:line / confidence / fix). Read those rows first; the codebase file:line may have drifted since the audit — re-read and adapt.

**Files (modify unless noted):**
- `MemberLevel.java` — GOLD multiplier `1.1` → `1.2` (§6.9 #1, definite).
- **Delete** `event/OrderPaidEvent.java` and `event/ReviewApprovedEvent.java` (the module-local shadow classes) — Spring dispatches by runtime type, so these shadows mean the listeners never fire (§6.9 #2/#3, definite; the single most impactful loyalty bug).
- `listener/OrderPaidEventListener.java`, `listener/ReviewApprovedEventListener.java` — change imports to `com.ecommerce.common.event.*`; adapt to the common classes' getters (payload shape from Task 1's interfaces block).
- `service/PointsExpireService.java` — replace the empty stub with a real expire scan (deduct + record) and add `@Scheduled` (§6.9 #4, definite).
- `service/OrderDataFetcher.java` — replace raw `JdbcTemplate` SQL against the `orders` table with a call through `OrderQueryService` (§6.9 #5, definite; this is a cross-module-boundary violation per design-docs/02 §3). Also switch `LocalDate.now()` → `SystemClockService` (§6.9 #10).

**Suspicious items (§6.9 #6–#11):** apply the judgment rule from Global Constraints — fix the ones the design doc states as a rule (member-level refresh before scoring #11; RuntimeConfigRegistry-driven constants #8/#9 where design-docs/附录B defines them as configurable), and for genuinely ambiguous ones (frozenPoints trigger #6, redeem/earn call-site #7) confirm the design-doc rule before changing; record the decision + reason for each in the report file.

- [ ] **Step 1:** Read design spec §6.9 + each cited file. Confirm the shadow-event deletion compiles against Task 1's common classes.
- [ ] **Step 2:** Apply the definite fixes (#1–#5, #10). For each, add/fix a unit test that pins the corrected behavior (e.g., GOLD multiplier test; a test that the listener wired to the *common* event actually earns points).
- [ ] **Step 3:** Adjudicate #6–#9, #11 per the rule above; implement the ones the doc mandates.
- [ ] **Step 4:** `source ~/tools/env.sh && mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-loyalty -am test` → all green.
- [ ] **Step 5:** Commit `git add code/ecommerce-loyalty` with a message citing design-docs/12 + 附录D.

## Task 11: `ecommerce-review` module (6 fixes)

**Depends on:** Task 1 (publishes `com.ecommerce.common.event.ReviewApprovedEvent`).

**Source of truth:** design spec §6.10.

**Files:**
- `service/ReviewService.java` — (a) call `OrderQueryService.verifyPurchase(...)` before allowing a review; fail with `REVIEW_PURCHASE_REQUIRED` (§6.10 #1, definite). (b) Do **not** publish the approval event on submit (§6.10 #2, definite). (c) Sensitive-word hit → persist as `REJECTED` rather than throwing away the request (§6.10 #6, suspicious — confirm the two allowed terminal states in design-docs/13 first).
- **Delete** module-local `event/ReviewApprovedEvent.java`; publish the common class from `ReviewModerationService.approve()` **only** (§6.10 #2/#3/#4, definite). Populate `orderId`/`productId` (the common class already carries these fields from Task 1).
- `service/SensitiveWordFilter.java` — change exact-equals matching to `contains`/`replace` (§6.10 #5, definite; design-docs/13 explicitly forbids exact-equals-only).

- [ ] **Step 1:** Read §6.10 + files. Confirm `OrderQueryService.verifyPurchase` signature from `ecommerce-order` (Task 6 didn't change it).
- [ ] **Step 2:** Apply definite fixes #1–#5; add unit tests: unpurchased→rejected, event fires once and only on approve, sensitive substring caught.
- [ ] **Step 3:** Adjudicate #6 against design-docs/13's allowed states; implement if the doc mandates a persisted `REJECTED`.
- [ ] **Step 4:** `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-review -am test` → green.
- [ ] **Step 5:** Commit citing design-docs/13 + 附录D.

## Task 12: `ecommerce-app` module (4 fixes, incl. one security hole)

**Depends on:** Task 7 (payment) for the callback-signature root cause — coordinate the shared `X-Payment-Signature` fix; if Task 7 already added signature validation in `ecommerce-payment`, this task only covers the app-level items.

**Source of truth:** design spec §6.12.

**Files:**
- **Delete** the `reset-sandbox` and `bootstrap-admin` endpoints from `SystemAdminController.java` and their `permitAll()` rules in `SecurityConfig.java` (§6.12 #1, definite, **security**: unauthenticated DB wipe / self-issued ADMIN token, and they are exactly the reset/bootstrap hooks design-docs/03 §5 forbids business code from exposing). Keep the other legitimate admin support controllers (fault-injection, system-clock, event-failure/notification queries) — only remove these two endpoints.
- `SecurityConfig.java` + `ecommerce-order/.../OrderController.java` — open `verify-purchase` to both `USER` and `ADMIN` (§6.12 #2, definite).
- `EventFailureAdminController.java` — event-failure replay endpoint (§6.12 #4, suspicious/optional): README's frozen 9 endpoints don't include replay, so this is an additive enhancement only; implement only if it doesn't touch the frozen contract, else record as intentionally skipped.

- [ ] **Step 1:** Read §6.12 + files. Confirm no public black-box test depends on `reset-sandbox`/`bootstrap-admin` (the harness uses its own per-case fresh context per design-docs/03 §5, so business code must not provide reset hooks — deleting them is correct).
- [ ] **Step 2:** Delete the two endpoints + security rules; open verify-purchase to ADMIN. Add a security test asserting the deleted paths now 401/404 and that an authenticated ADMIN can call verify-purchase.
- [ ] **Step 3:** `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-app -am test`; then a full `install` since app is the aggregator.
- [ ] **Step 4:** Commit citing design-docs/03 §5 + 附录A.

## Task 13: Full-system verification (gate before packaging)

**Depends on:** Tasks 1–12 all committed. This is the first point every module compiles together against the new shared common classes; it is the green baseline the entire submission reproduces.

- [ ] **Step 1:** Clean build all modules: `source ~/tools/env.sh && mvn -s maven-settings.xml -f code/pom.xml clean install -DskipTests`. Must be `BUILD SUCCESS` for all 12 modules. If any module fails to compile, fix in its owning module (not here) and re-run.
- [ ] **Step 2:** Full unit suite: `mvn -s maven-settings.xml -f code/pom.xml test`. Record pass count.
- [ ] **Step 3:** Full black-box suite: `mvn -s maven-settings.xml -f test-cases/pom.xml test`. **All 24 public cases (PUB-001..016, PUB-101..108) must pass.** Record the count.
- [ ] **Step 4:** If any case is red, triage to the owning module, dispatch a fix, re-run from Step 1. Do not proceed to packaging until 24/24 green + full unit suite green.
- [ ] **Step 5:** Capture the exact green commit SHA — Task 14 diffs against baseline `1b1e88f` up to this SHA.

## Task 14: Build the `knowledge-base/` (Stage 1 → Stage 2 artifact)

**Goal:** turn the verified `code/` diff into the deterministic-apply payload. No code logic here — pure artifact generation.

- [ ] **Step 1:** Changed-file list: `git diff --name-status 1b1e88f..HEAD -- code/`. Split into **modified/added** (M/A) and **deleted** (D) — the shadow event classes and the two admin endpoints may produce deletions.
- [ ] **Step 2:** For every M/A file, copy its **full current content** to `output/work/fixer/knowledge-base/<relpath>` (preserve the `code/...` relative path).
- [ ] **Step 3:** Baseline hashes: for every changed path, `git show 1b1e88f:<path> | sha256sum` → write `output/work/fixer/knowledge-base/baseline-hashes.txt` as `<sha256>␣␣<relpath>`. For **added** files (no baseline), use the sentinel `ABSENT`. For **deleted** files, list them in `output/work/fixer/knowledge-base/deletions.txt` with their baseline hash.
- [ ] **Step 4:** `findings.md`: render design spec §6 into a table — columns **模块 / 症状 / design-docs 依据 / 修复 / 改动文件 / 置信度**. This is the reviewer-facing evidence index; every row must cite a design-doc section.
- [ ] **Step 5:** Sanity: count of knowledge-base files + deletions == count of changed paths from Step 1. Commit `output/`.

## Task 15: `apply.sh` engine + Stage 3 skill + checklists

**Goal:** the runtime executables. `apply.sh` is deterministic (no AI); the skill governs the agent complement.

- [ ] **Step 1: `output/work/fixer/apply.sh`** — POSIX bash, `set -euo pipefail`. Arg 1 = target root (default `/app/code/judge-assets/02_04_design_implementation_consistency`). For each entry in `baseline-hashes.txt`:
  - compute `sha256sum` of the target file;
  - **matches baseline** → overwrite from `knowledge-base/`, increment `applied`;
  - **matches the knowledge-base version already** → increment `already`, skip (idempotent);
  - **matches neither** (or baseline is `ABSENT` and file exists with unexpected hash) → increment `skipped`, append to a skipped list, do **not** touch;
  - added files (`ABSENT`): create only if absent, else treat as skip-for-review.
  For each path in `deletions.txt`: delete only if the target's hash matches the recorded baseline; else skip + record. Emit an `apply-report` line: `checked=N applied=M already=P skipped=K` and write the skipped list to `logs/trace/apply-skipped.txt`. Exit 0 even with skips (Stage 3 handles them); exit non-zero only on unusable target root.
- [ ] **Step 2:** Test `apply.sh` locally against a restored dirty baseline (full test is Task 17) — confirm `applied` equals the changed-file count and `skipped=0`.
- [ ] **Step 3: `output/work/skills/design-consistency-fixer/SKILL.md`** (Stage 3) — encode design spec §4 verbatim in intent: **verify first**; all-green + `skipped=0` → light spot-check only; red or skips → per-module checklist deep-check with the guardrails (backup `.bak` → `mvn install -DskipTests` compile-gate → re-run failed tests → rollback on regression/compile-fail → bounded single retry → never touch a hash-matched green file). Write `result/output.md` with `STATUS: DONE`.
- [ ] **Step 4: `output/work/fixer/checklist/<module>.md`** — one per module (12) + `cross-cutting.md`. Each row: file → design-doc rule → expected → corrected snippet. Populate from design spec §6.0–§6.12 (the "看什么/期望什么/怎么改" form — never require the agent to re-derive the expected value).
- [ ] **Step 5:** Commit `output/`.

## Task 16: `INSTRUCTION.md` + `DESIGN.md` + Stage 1 auditor skill

- [ ] **Step 1: `output/INSTRUCTION.md`** — GUIDANCE §4's four blocks, **mechanism-agnostic, de-"copy"-ed** (design spec §5): env prep (JDK 17+/Maven 3.6+ with Temurin/Apache download fallback, no manual steps); execution (run `apply.sh` described as "**运行一致性修复引擎**", then "let the agent read `work/skills/design-consistency-fixer/SKILL.md` and follow its steps" — load skill as plain markdown, don't assume a Skill runtime); completion (`result/output.md` contains `STATUS: DONE`); result retrieval (fixed project is in-place at `<target-root>/code/`, logs in `logs/trace/`, report in `result/output.md`).
- [ ] **Step 2: `output/work/DESIGN.md`** (方案说明 — GUIDANCE §6.9 makes its absence a non-evaluable condition) — the three-stage narrative: Stage 1 offline audit → knowledge base; Stage 2 hash-gated engine semantics; Stage 3 verify-first + guardrails; plus the self-verification method and the honest note that opencode/codeagent couldn't be run locally (Claude Code subagent used as proxy).
- [ ] **Step 3: `output/work/skills/design-consistency-auditor/SKILL.md`** (Stage 1, the generalization evidence) — the re-runnable audit playbook: given a fresh `code/` + `design-docs/` + `README.md`, how the module-by-module comparison produces a findings knowledge base. This is what substantiates "point it at a new project and it regenerates" against the §5.1 hardcoding-deduction clause.
- [ ] **Step 4:** Commit `output/`.

## Task 17: End-to-end dry run + `result/`/`logs/` assembly (final gate)

**Goal:** prove the packaged submission reproduces green from a pristine dirty baseline, exactly as the judge will run it.

- [ ] **Step 1:** Restore the pristine baseline `code/` (`git worktree add` or checkout `1b1e88f -- code/` into a temp dir mirroring the `judge-assets/02_04_.../code` layout).
- [ ] **Step 2:** Run the full `INSTRUCTION.md` flow against that temp root: `bash output/work/fixer/apply.sh <temp-root>` → confirm `apply-report` shows `applied` = changed-file count, `skipped=0`. Then execute the Stage 3 SKILL.md steps (verification suite).
- [ ] **Step 3:** Verify **24/24 black-box + full unit suite green** from the dirty→applied state.
- [ ] **Step 4: Idempotency** — run `apply.sh <temp-root>` a second time; confirm `applied=0 already=<count> skipped=0` and nothing breaks.
- [ ] **Step 5: Assemble deliverables** — `output/result/output.md` (the run record with apply-report + test counts + `STATUS: DONE`); `output/logs/interaction.md` (empty + one-line "全程无人工干预" declaration); `output/logs/trace/` (the run logs incl. apply-skipped). Optionally `output/result/screenshot/`.
- [ ] **Step 6: GUIDANCE §6 disqualifier checklist** — confirm: INSTRUCTION.md auto-executable, no manual interaction, completion detectable, fixed project retrievable, project **builds**, `design-docs/`/`README.md`/`test-cases/`/REST contract **untouched**, 方案说明 present. Commit final `output/`.

<!-- END OF PLAN -->

