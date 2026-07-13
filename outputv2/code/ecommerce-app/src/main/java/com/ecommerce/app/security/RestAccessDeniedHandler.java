package com.ecommerce.app.security;

import com.ecommerce.common.dto.ApiError;
import com.ecommerce.common.exception.AuthorizationException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

/**
 * Writes the standard {@code {code,message,traceId,details}} error body for
 * requests rejected by Spring Security for insufficient role (authenticated
 * but wrong role) — see {@link RestAuthenticationEntryPoint} for the sibling
 * missing-authentication case.
 */
@Component
public class RestAccessDeniedHandler implements AccessDeniedHandler {

    private final ObjectMapper objectMapper;

    public RestAccessDeniedHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                        AccessDeniedException accessDeniedException) throws IOException {
        String traceId = UUID.randomUUID().toString().substring(0, 8) + "-" + System.currentTimeMillis();
        ApiError error = new ApiError(AuthorizationException.CODE_FORBIDDEN,
                "You do not have permission to access this resource", traceId, null);
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(objectMapper.writeValueAsString(error));
    }
}
