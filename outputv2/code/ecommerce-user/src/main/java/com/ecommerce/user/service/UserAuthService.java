package com.ecommerce.user.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.user.dto.ActivateRequest;
import com.ecommerce.user.dto.LoginRequest;
import com.ecommerce.user.dto.LoginResponse;
import com.ecommerce.user.dto.UserResponse;
import com.ecommerce.user.entity.EmailActivationToken;
import com.ecommerce.user.entity.LoginSession;
import com.ecommerce.user.entity.User;
import com.ecommerce.user.entity.UserStatus;
import com.ecommerce.user.repository.EmailActivationTokenRepository;
import com.ecommerce.user.repository.LoginSessionRepository;
import com.ecommerce.user.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;

/**
 * Handles authentication: login, email activation, freeze/unfreeze.
 */
@Service
public class UserAuthService {

    private static final Logger log = LoggerFactory.getLogger(UserAuthService.class);

    private final UserRepository userRepository;
    private final EmailActivationTokenRepository activationTokenRepository;
    private final LoginSessionRepository loginSessionRepository;
    private final BCryptPasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final AuditLogService auditLogService;

    public UserAuthService(UserRepository userRepository,
                           EmailActivationTokenRepository activationTokenRepository,
                           LoginSessionRepository loginSessionRepository,
                           BCryptPasswordEncoder passwordEncoder,
                           JwtTokenProvider jwtTokenProvider,
                           AuditLogService auditLogService) {
        this.userRepository = userRepository;
        this.activationTokenRepository = activationTokenRepository;
        this.loginSessionRepository = loginSessionRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
        this.auditLogService = auditLogService;
    }

    /**
     * Authenticates a user by email (or nickname) and password.
     * design-docs/04 §4: login validates "用户名或邮箱存在" — the request's email
     * field doubles as a username/nickname (see {@link LoginRequest}), so an
     * email miss falls back to a nickname lookup before reporting not-found.
     */
    @Transactional
    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .or(() -> userRepository.findFirstByNicknameOrderByIdAsc(request.getEmail()))
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + request.getEmail()));

        if (user.getStatus() != UserStatus.ACTIVE) {
            if (user.getStatus() == UserStatus.FROZEN) {
                throw new AuthorizationException("USER_FROZEN", "Account is frozen: " + user.getEmail());
            }
            throw new AuthorizationException("USER_NOT_ACTIVE", "Account is not active: " + user.getEmail());
        }

        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new AuthorizationException("UNAUTHORIZED", "Invalid password");
        }

        List<String> roles = Collections.singletonList(user.getRole().name());
        String token = jwtTokenProvider.generateToken(user.getId(), roles);

        // Record login session
        LoginSession session = new LoginSession();
        session.setUserId(user.getId());
        session.setToken(token);
        session.setLoginTime(LocalDateTime.now());
        session.setExpiresAt(LocalDateTime.now().plusMinutes(120));
        loginSessionRepository.save(session);

        log.info("User logged in: id={}, email={}", user.getId(), user.getEmail());
        return new LoginResponse(token, user.getId(), roles);
    }

    /**
     * Activates a user account using an email activation token.
     */
    @Transactional
    public UserResponse activate(ActivateRequest request) {
        EmailActivationToken activationToken = activationTokenRepository.findByToken(request.getToken())
                .orElseThrow(() -> new ResourceNotFoundException("Invalid or expired activation token"));

        if (activationToken.isUsed()) {
            throw new ConflictException("Activation token has already been used");
        }

        if (activationToken.getExpiresAt().isBefore(SystemClockService.now())) {
            throw new ConflictException("Activation token has expired");
        }

        User user = userRepository.findById(activationToken.getUserId())
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + activationToken.getUserId()));

        user.setStatus(UserStatus.ACTIVE);
        userRepository.save(user);

        activationToken.setUsed(true);
        activationTokenRepository.save(activationToken);

        log.info("User activated: id={}, email={}", user.getId(), user.getEmail());
        return UserResponse.from(user);
    }

    /**
     * Freezes a user account, preventing login and ordering.
     */
    @Transactional
    public void freezeUser(Long userId, String operatorId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
        UserStatus before = user.getStatus();
        user.setStatus(UserStatus.FROZEN);
        userRepository.save(user);
        auditLogService.record(operatorId, "USER_FREEZE", String.valueOf(userId),
                before.name(), UserStatus.FROZEN.name(), null);
        log.info("User frozen: id={}", userId);
    }

    /**
     * Unfreezes (reactivates) a previously frozen user account.
     */
    @Transactional
    public void unfreezeUser(Long userId, String operatorId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + userId));
        UserStatus before = user.getStatus();
        user.setStatus(UserStatus.ACTIVE);
        userRepository.save(user);
        auditLogService.record(operatorId, "USER_UNFREEZE", String.valueOf(userId),
                before.name(), UserStatus.ACTIVE.name(), null);
        log.info("User unfrozen: id={}", userId);
    }
}
