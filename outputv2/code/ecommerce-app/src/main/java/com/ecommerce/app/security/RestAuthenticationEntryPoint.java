package com.ecommerce.app.security;

import com.ecommerce.common.dto.ApiError;
import com.ecommerce.common.exception.AuthorizationException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

/**
 * Writes the standard {@code {code,message,traceId,details}} error body for
 * requests rejected by Spring Security's filter chain (missing/invalid token)
 * before they ever reach a controller — this path never goes through
 * {@link com.ecommerce.common.exception.GlobalExceptionHandler}, so without
 * this entry point the response falls back to Spring Security's default
 * 403 + non-contract body for what should be a 401.
 */
@Component
public class RestAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final ObjectMapper objectMapper;

    public RestAuthenticationEntryPoint(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                          AuthenticationException authException) throws IOException {
        String traceId = UUID.randomUUID().toString().substring(0, 8) + "-" + System.currentTimeMillis();
        ApiError error = new ApiError(AuthorizationException.CODE_UNAUTHORIZED,
                "Authentication is required to access this resource", traceId, null);
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(objectMapper.writeValueAsString(error));
    }
}
