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
