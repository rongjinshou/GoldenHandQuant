package com.ecommerce.common.audit;

import com.ecommerce.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

/**
 * Shared audit log entry recorded for sensitive operations across modules
 * (design-docs/03 section 6): user freeze/unfreeze, product on/off shelf,
 * manual inventory adjustment, order cancellation review, refund review and
 * warehouse acceptance, invoice issuance, and settlement batch generation.
 */
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
