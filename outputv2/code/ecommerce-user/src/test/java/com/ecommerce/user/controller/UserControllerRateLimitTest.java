package com.ecommerce.user.controller;

import com.ecommerce.common.exception.GlobalExceptionHandler;
import com.ecommerce.common.ratelimit.RateLimitAspect;
import com.ecommerce.user.config.TestSecurityConfig;
import com.ecommerce.user.dto.LoginRequest;
import com.ecommerce.user.dto.LoginResponse;
import com.ecommerce.user.repository.UserRepository;
import com.ecommerce.user.service.JwtTokenProvider;
import com.ecommerce.user.service.UserAuthService;
import com.ecommerce.user.service.UserRegisterService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.EnableAspectJAutoProxy;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Verifies the login endpoint's rate limit (design-docs/03 section 4: "登录 | 同一用户名每分钟 5 次").
 *
 * <p>Kept separate from {@link UserControllerTest} because it needs
 * {@link RateLimitAspect} plus AspectJ auto-proxying wired into the slice
 * context (neither is part of the curated {@code @WebMvcTest} auto-configuration,
 * and neither is needed by this module's other controller tests), and
 * {@link GlobalExceptionHandler} to translate the resulting
 * {@code RateLimitException} into an HTTP 429 response.
 */
@WebMvcTest(UserController.class)
@Import({JwtTokenProvider.class, TestSecurityConfig.class, RateLimitAspect.class, GlobalExceptionHandler.class})
@EnableAspectJAutoProxy
@TestPropertySource(properties = {
        "security.jwt.secret=0123456789abcdef0123456789abcdef",
        "security.jwt.issuer=test-issuer",
        "security.jwt.expire-minutes=120"
})
@DisplayName("UserController login rate limit")
class UserControllerRateLimitTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private UserRegisterService userRegisterService;

    @MockBean
    private UserAuthService userAuthService;

    @MockBean
    private UserRepository userRepository;

    @Test
    @DisplayName("allows the first 5 login attempts for an email and rejects the 6th with 429")
    void login_sixthAttemptWithinAMinute_returns429() throws Exception {
        when(userAuthService.login(any())).thenReturn(new LoginResponse("jwt-token", 1L, List.of("USER")));

        LoginRequest request = new LoginRequest();
        request.setEmail("ratelimit-test@example.com");
        request.setPassword("wrong-password");
        String body = objectMapper.writeValueAsString(request);

        for (int i = 0; i < 5; i++) {
            mockMvc.perform(post("/api/v1/users/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(body))
                    .andExpect(status().isOk());
        }

        mockMvc.perform(post("/api/v1/users/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isTooManyRequests());
    }

    @Test
    @DisplayName("rate limit is scoped per email; a different email is unaffected by another email's limit")
    void login_differentEmails_haveIndependentLimits() throws Exception {
        when(userAuthService.login(any())).thenReturn(new LoginResponse("jwt-token", 1L, List.of("USER")));

        LoginRequest exhausted = new LoginRequest();
        exhausted.setEmail("exhausted-user@example.com");
        exhausted.setPassword("wrong-password");
        String exhaustedBody = objectMapper.writeValueAsString(exhausted);

        for (int i = 0; i < 5; i++) {
            mockMvc.perform(post("/api/v1/users/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(exhaustedBody))
                    .andExpect(status().isOk());
        }
        mockMvc.perform(post("/api/v1/users/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(exhaustedBody))
                .andExpect(status().isTooManyRequests());

        LoginRequest freshEmail = new LoginRequest();
        freshEmail.setEmail("fresh-user@example.com");
        freshEmail.setPassword("wrong-password");

        mockMvc.perform(post("/api/v1/users/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(freshEmail)))
                .andExpect(status().isOk());
    }
}
