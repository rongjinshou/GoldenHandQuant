package com.ecommerce.user.service;

import com.ecommerce.common.test.SystemClockService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jws;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.ZoneId;
import java.util.Collections;
import java.util.Date;
import java.util.List;

/**
 * JWT token provider that generates and validates HMAC-SHA256 tokens.
 */
@Component
public class JwtTokenProvider {

    private final SecretKey secretKey;
    private final String issuer;
    private final long expireMinutes;

    public JwtTokenProvider(
            @Value("${security.jwt.secret}") String secret,
            @Value("${security.jwt.issuer}") String issuer,
            @Value("${security.jwt.expire-minutes}") long expireMinutes) {
        this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.issuer = issuer;
        this.expireMinutes = expireMinutes;
    }

    /**
     * Generates a JWT token containing userId and roles claims.
     * iat/exp are taken from the test-support clock ({@link SystemClockService}),
     * not the wall clock, so an admin-shifted system time is reflected in tokens.
     */
    public String generateToken(Long userId, List<String> roles) {
        Date now = clockNow();
        Date expiration = new Date(now.getTime() + expireMinutes * 60 * 1000);

        return Jwts.builder()
                .issuer(issuer)
                .subject(String.valueOf(userId))
                .claim("roles", roles)
                .issuedAt(now)
                .expiration(expiration)
                .signWith(secretKey)
                .compact();
    }

    /**
     * Validates and parses a JWT token, returning the claims.
     * The parser's expiry check runs off the same {@link SystemClockService}
     * source as token issuance (jjwt 0.12 {@code JwtParserBuilder.clock}),
     * keeping both sides of the JWT lifecycle on one coherent clock.
     */
    public Jws<Claims> validateToken(String token) {
        return Jwts.parser()
                .verifyWith(secretKey)
                .requireIssuer(issuer)
                .clock(JwtTokenProvider::clockNow)
                .build()
                .parseSignedClaims(token);
    }

    /**
     * Current instant per {@link SystemClockService}, converted to the legacy
     * {@link Date} the jjwt API expects.
     */
    private static Date clockNow() {
        return Date.from(SystemClockService.now().atZone(ZoneId.systemDefault()).toInstant());
    }

    /**
     * Extracts the userId from a parsed JWT token.
     */
    public Long getUserId(Jws<Claims> claims) {
        return Long.parseLong(claims.getPayload().getSubject());
    }

    /**
     * Extracts the roles from a parsed JWT token.
     */
    @SuppressWarnings("unchecked")
    public List<String> getRoles(Jws<Claims> claims) {
        List<String> roles = claims.getPayload().get("roles", List.class);
        return roles != null ? roles : Collections.emptyList();
    }
}
