package com.ecommerce.user.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

/**
 * Provides the {@link BCryptPasswordEncoder} bean consumed directly (by
 * concrete type) by {@code UserRegisterService}/{@code UserAuthService}.
 * <p>
 * The actual {@code SecurityFilterChain} for the whole application is
 * defined once, centrally, in {@code ecommerce-app}'s {@code SecurityConfig}
 * (design-docs/02: app-bootstrap owns Spring Security configuration). This
 * class used to also declare its own filter chain bean, which coexisted with
 * app's — since neither had a {@code securityMatcher()}/{@code @Order}, which
 * chain actually applied to a given request depended on Spring's internal
 * bean-registration order, a fragile setup that could silently flip after any
 * dependency/classpath change.
 */
@Configuration
public class SecurityConfig {

    @Bean
    public BCryptPasswordEncoder bCryptPasswordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
