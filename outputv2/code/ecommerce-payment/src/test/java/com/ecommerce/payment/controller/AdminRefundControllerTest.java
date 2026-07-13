package com.ecommerce.payment.controller;

import com.ecommerce.payment.dto.RefundResponse;
import com.ecommerce.payment.dto.RefundReviewRequest;
import com.ecommerce.payment.entity.RefundStatus;
import com.ecommerce.payment.service.RefundService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AdminRefundController.class)
@AutoConfigureMockMvc(addFilters = false)
class AdminRefundControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private RefundService refundService;

    // ---- POST /api/v1/admin/refunds/{refundId}/review -> 200 ----

    @Test
    @WithMockUser(username = "999", roles = {"ADMIN"})
    @DisplayName("POST /api/v1/admin/refunds/{refundId}/review should return 200")
    void postReview_shouldReturn200() throws Exception {
        Long refundId = 1L;
        RefundReviewRequest request = new RefundReviewRequest(true, "Approved");

        // Approval moves the refund to WAITING_WAREHOUSE_ACCEPT — it must NOT
        // complete the refund directly (design-docs/09 §4).
        RefundResponse response = new RefundResponse();
        response.setId(refundId);
        response.setRefundNo("RF001");
        response.setPaymentNo("PAY123");
        response.setOrderId(1L);
        response.setUserId(100L);
        response.setRefundAmount(new BigDecimal("97.00"));
        response.setStatus(RefundStatus.WAITING_WAREHOUSE_ACCEPT);
        response.setReviewNote("Approved");

        when(refundService.reviewRefund(anyLong(), anyLong(), any(RefundReviewRequest.class)))
                .thenReturn(response);

        mockMvc.perform(post("/api/v1/admin/refunds/{refundId}/review", refundId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("WAITING_WAREHOUSE_ACCEPT"))
                .andExpect(jsonPath("$.refundNo").value("RF001"));

        verify(refundService).reviewRefund(anyLong(), anyLong(), any(RefundReviewRequest.class));
    }

    // ---- POST /api/v1/admin/refunds/{refundId}/warehouse-accept -> 200 ----

    @Test
    @WithMockUser(username = "999", roles = {"ADMIN"})
    @DisplayName("POST /api/v1/admin/refunds/{refundId}/warehouse-accept should return 200")
    void postWarehouseAccept_shouldReturn200() throws Exception {
        Long refundId = 1L;

        // warehouseAccept is the only path that completes a refund, after it
        // has been approved and moved to WAITING_WAREHOUSE_ACCEPT.
        // No body at all keeps the historical acceptance behavior.
        RefundResponse response = new RefundResponse();
        response.setId(refundId);
        response.setRefundNo("RF001");
        response.setStatus(RefundStatus.WAREHOUSE_ACCEPTED);

        when(refundService.warehouseAccept(anyLong(), anyLong()))
                .thenReturn(response);

        mockMvc.perform(post("/api/v1/admin/refunds/{refundId}/warehouse-accept", refundId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("WAREHOUSE_ACCEPTED"));

        verify(refundService).warehouseAccept(anyLong(), anyLong());
        verify(refundService, never()).warehouseReject(anyLong(), anyLong());
    }

    @Test
    @WithMockUser(username = "999", roles = {"ADMIN"})
    @DisplayName("warehouse-accept with {\"accepted\": true} body runs the acceptance flow")
    void postWarehouseAccept_acceptedTrue_runsAcceptFlow() throws Exception {
        Long refundId = 1L;

        RefundResponse response = new RefundResponse();
        response.setId(refundId);
        response.setRefundNo("RF001");
        response.setStatus(RefundStatus.WAREHOUSE_ACCEPTED);

        when(refundService.warehouseAccept(anyLong(), anyLong()))
                .thenReturn(response);

        // The black-box harness's RefundFixture#warehouseAccept always sends
        // {"accepted": true|false} as a JSON body.
        mockMvc.perform(post("/api/v1/admin/refunds/{refundId}/warehouse-accept", refundId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"accepted\": true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("WAREHOUSE_ACCEPTED"));

        verify(refundService).warehouseAccept(anyLong(), anyLong());
        verify(refundService, never()).warehouseReject(anyLong(), anyLong());
    }

    @Test
    @WithMockUser(username = "999", roles = {"ADMIN"})
    @DisplayName("warehouse-accept with {\"accepted\": false} body rejects the refund instead of completing it")
    void postWarehouseAccept_acceptedFalse_rejectsRefund() throws Exception {
        Long refundId = 1L;

        // accepted=false means the returned goods failed inspection: the
        // refund is REJECTED and the financial refund never runs (09 §4).
        RefundResponse response = new RefundResponse();
        response.setId(refundId);
        response.setRefundNo("RF001");
        response.setStatus(RefundStatus.REJECTED);

        when(refundService.warehouseReject(anyLong(), anyLong()))
                .thenReturn(response);

        mockMvc.perform(post("/api/v1/admin/refunds/{refundId}/warehouse-accept", refundId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"accepted\": false}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("REJECTED"));

        verify(refundService).warehouseReject(anyLong(), anyLong());
        verify(refundService, never()).warehouseAccept(anyLong(), anyLong());
    }
}
