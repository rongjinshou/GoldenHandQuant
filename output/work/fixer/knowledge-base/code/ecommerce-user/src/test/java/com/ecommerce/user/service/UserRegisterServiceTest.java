package com.ecommerce.user.service;

import com.ecommerce.common.exception.ConflictException;
import com.ecommerce.common.notification.LocalNotificationService;
import com.ecommerce.common.notification.NotificationChannel;
import com.ecommerce.common.notification.NotificationRequest;
import com.ecommerce.user.dto.RegisterRequest;
import com.ecommerce.user.dto.UserResponse;
import com.ecommerce.user.entity.User;
import com.ecommerce.user.entity.UserRole;
import com.ecommerce.user.entity.UserStatus;
import com.ecommerce.user.repository.EmailActivationTokenRepository;
import com.ecommerce.user.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("UserRegisterService")
class UserRegisterServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private BCryptPasswordEncoder passwordEncoder;

    @Mock
    private LocalNotificationService notificationService;

    @Mock
    private EmailActivationTokenRepository activationTokenRepository;

    @InjectMocks
    private UserRegisterService userRegisterService;

    private RegisterRequest validRequest() {
        RegisterRequest request = new RegisterRequest();
        request.setEmail("newuser@example.com");
        request.setPhone("13800138000");
        request.setPassword("securePass123");
        request.setNickname("NewUser");
        return request;
    }

    @Test
    @DisplayName("registers a new user and returns UserResponse with PENDING_ACTIVATION status")
    void testRegister_newUser_returnsUserResponse() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(userRepository.existsByPhone(request.getPhone())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("$2a$10$hashed");

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User u = invocation.getArgument(0);
            u.setId(1L);
            return u;
        });

        UserResponse response = userRegisterService.register(request);

        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();

        assertThat(response.getUserId()).isEqualTo(1L);
        assertThat(response.getEmail()).isEqualTo("newuser@example.com");
        assertThat(response.getPhone()).isEqualTo("13800138000");
        assertThat(response.getNickname()).isEqualTo("NewUser");
        assertThat(response.getStatus()).isEqualTo(UserStatus.PENDING_ACTIVATION);
        assertThat(response.getRole()).isEqualTo(UserRole.USER);

        assertThat(savedUser.getEmail()).isEqualTo("newuser@example.com");
        assertThat(savedUser.getPasswordHash()).isEqualTo("$2a$10$hashed");
        assertThat(savedUser.getStatus()).isEqualTo(UserStatus.PENDING_ACTIVATION);
        assertThat(savedUser.getRole()).isEqualTo(UserRole.USER);
    }

    @Test
    @DisplayName("throws ConflictException when email is already registered")
    void testRegister_duplicateEmail_throwsException() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(true);

        assertThatThrownBy(() -> userRegisterService.register(request))
                .isInstanceOf(ConflictException.class)
                .hasMessageContaining("Email already registered");
    }

    @Test
    @DisplayName("hashes the password before saving the user")
    void testRegister_passwordIsHashed() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(userRepository.existsByPhone(request.getPhone())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("$2a$10$encryptedPassword");

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User u = invocation.getArgument(0);
            u.setId(1L);
            return u;
        });

        userRegisterService.register(request);

        verify(passwordEncoder).encode("securePass123");
        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertThat(savedUser.getPasswordHash()).isEqualTo("$2a$10$encryptedPassword");
        assertThat(savedUser.getPasswordHash()).isNotEqualTo("securePass123");
    }

    @Test
    @DisplayName("sends activation email notification via LocalNotificationService after registration")
    void testRegister_notificationSent() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(userRepository.existsByPhone(request.getPhone())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("$2a$10$hashed");

        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User u = invocation.getArgument(0);
            u.setId(1L);
            u.setEmail(request.getEmail());
            u.setNickname(request.getNickname());
            return u;
        });

        userRegisterService.register(request);

        ArgumentCaptor<NotificationRequest> notificationCaptor =
                ArgumentCaptor.forClass(NotificationRequest.class);
        verify(notificationService).send(notificationCaptor.capture());

        NotificationRequest notification = notificationCaptor.getValue();
        assertThat(notification.getBizType()).isEqualTo("USER_REGISTER");
        assertThat(notification.getBizId()).isEqualTo("1");
        assertThat(notification.getReceiver()).isEqualTo("newuser@example.com");
        assertThat(notification.getChannel()).isEqualTo(NotificationChannel.EMAIL);
        assertThat(notification.getTemplateCode()).isEqualTo("activation_email");
        assertThat(notification.getVariables()).containsEntry("nickname", "NewUser");
        assertThat(notification.getVariables()).containsKey("activationToken");
    }

    @Test
    @DisplayName("sets user status to PENDING_ACTIVATION (not ACTIVE) on registration")
    void testRegister_userStatusAfterRegistration() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(userRepository.existsByPhone(request.getPhone())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("$2a$10$hashed");

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User u = invocation.getArgument(0);
            u.setId(1L);
            return u;
        });

        userRegisterService.register(request);

        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertThat(savedUser.getStatus()).isEqualTo(UserStatus.PENDING_ACTIVATION);
        assertThat(savedUser.getStatus()).isNotEqualTo(UserStatus.ACTIVE);
    }

    @Test
    @DisplayName("creates and persists an EmailActivationToken for the new user")
    void testRegister_createsActivationToken() {
        RegisterRequest request = validRequest();
        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(userRepository.existsByPhone(request.getPhone())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("$2a$10$hashed");
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User u = invocation.getArgument(0);
            u.setId(1L);
            return u;
        });

        userRegisterService.register(request);

        ArgumentCaptor<com.ecommerce.user.entity.EmailActivationToken> tokenCaptor =
                ArgumentCaptor.forClass(com.ecommerce.user.entity.EmailActivationToken.class);
        verify(activationTokenRepository).save(tokenCaptor.capture());

        com.ecommerce.user.entity.EmailActivationToken savedToken = tokenCaptor.getValue();
        assertThat(savedToken.getUserId()).isEqualTo(1L);
        assertThat(savedToken.getToken()).isNotBlank();
        assertThat(savedToken.isUsed()).isFalse();
        assertThat(savedToken.getExpiresAt()).isAfter(java.time.LocalDateTime.now());
    }
}
