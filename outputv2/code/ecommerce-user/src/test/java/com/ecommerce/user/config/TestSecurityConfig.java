package com.ecommerce.user.config;

import com.ecommerce.user.security.JwtAuthFilter;
import com.ecommerce.user.service.JwtTokenProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Test-only {@code SecurityFilterChain} for isolated {@code @WebMvcTest} slices
 * in this module. The real application uses a single, centrally-defined chain
 * in {@code ecommerce-app}'s {@code SecurityConfig} (which this module's tests
 * cannot depend on, since {@code ecommerce-app} depends on {@code ecommerce-user}
 * and not the reverse) — this class exists purely so module-local controller
 * slice tests can exercise {@link JwtAuthFilter} handling without booting the
 * whole application.
 */
@Configuration
@EnableWebSecurity
public class TestSecurityConfig {

    private final JwtTokenProvider jwtTokenProvider;

    public TestSecurityConfig(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session ->
                        session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/v1/users/register").permitAll()
                        .requestMatchers("/api/v1/users/activate").permitAll()
                        .requestMatchers("/api/v1/users/login").permitAll()
                        .requestMatchers("/api/v1/products/**").permitAll()
                        .requestMatchers("/api/v1/categories/**").permitAll()
                        .requestMatchers("/api/v1/inventory/**").permitAll()
                        .requestMatchers("/api/v1/reviews/product/**").permitAll()
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                        .anyRequest().authenticated()
                )
                .addFilterBefore(new JwtAuthFilter(jwtTokenProvider),
                        UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
