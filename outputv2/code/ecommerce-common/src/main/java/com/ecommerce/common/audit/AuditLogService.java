package com.ecommerce.common.audit;

import org.springframework.stereotype.Service;

/**
 * Shared service for recording audit log entries (design-docs/03 section 6).
 * Business modules call {@link #record} for every audited operation; each
 * call site's audit point is tracked per-module in the tasks that wire it in.
 */
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
