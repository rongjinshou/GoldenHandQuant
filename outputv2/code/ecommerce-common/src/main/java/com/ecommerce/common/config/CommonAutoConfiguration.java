package com.ecommerce.common.config;

import com.ecommerce.common.test.SystemClockService;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.auditing.DateTimeProvider;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

import java.util.Optional;

/**
 * Auto-configuration for the ecommerce-common module.
 * Enables JPA auditing and component scanning for the common package
 * so that other modules only need to depend on this module's artifact.
 *
 * <p>JPA auditing is wired to {@link SystemClockService} (design-docs/01
 * 「测试时钟纳入 API 契约」/ design-docs/03 §5): every {@code createdAt}/
 * {@code updatedAt} audit stamp must follow the adjustable test clock, so
 * that clock-shift test cases (e.g. sales statistics bucketed by
 * {@code createdAt}) observe entities in the shifted day-bucket instead of
 * the real wall clock. When the clock is not shifted the provider is
 * identical to {@code LocalDateTime.now()}.
 */
@Configuration
@EnableJpaAuditing(dateTimeProviderRef = "systemClockDateTimeProvider")
@ComponentScan(basePackages = "com.ecommerce.common")
public class CommonAutoConfiguration {

    @Bean
    public DateTimeProvider systemClockDateTimeProvider() {
        return () -> Optional.of(SystemClockService.now());
    }
}
