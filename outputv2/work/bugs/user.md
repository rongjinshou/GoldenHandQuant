# B02 · user — 注册激活 / 登录错误语义 / 地址 / 安全配置去重

本批覆盖 `ecommerce-user` 模块 5 处行为缺陷 + 1 处跨模块（user + app）安全配置结构性问题：注册后跳过邮箱激活直接 `ACTIVE`、登录对未激活/冻结用户返回错误的 HTTP 语义、地址格式化方法参数顺序违反冻结签名、地址 `isDefault` 字段的 JSON key 被 Jackson 静默改名、激活令牌复用/过期返回错误的 HTTP 语义、以及 user 模块与 app 模块并存两份 `SecurityFilterChain` bean 的脆弱配置。"改法"/"验收"对照已通过 24/24 黑盒验证（17+ 次重复独立运行）的参考实现逐行核对——卡片里给出的目标代码即该参考实现的最终内容。

本文件**不包含**以下同属 user 模块、但归其他批次负责的条目——`code/ecommerce-user` 下同一批文件可能会被其他批次的卡片继续编辑，这是预期行为，本批不要抢先实现：

- **冻结/解冻缺审计日志**（findings.md「user 模块 §6.1」#5）→ `S3-audit.md`（B18）。会把 `UserAuthService.freezeUser(Long)`/`unfreezeUser(Long)` 改签名为 `freezeUser(Long, String operatorId)`/`unfreezeUser(Long, String operatorId)` 并接入新的 `AuditLogService`，连带改 `AdminUserController`（追加 `Authentication` 参数）和 `AdminUserControllerTest` 的 `verify(...)` 断言。本批的 USER-2/USER-5 也改 `UserAuthService.java`/`UserAuthServiceTest.java`，但只碰 `login()`/`activate()` 区域，与 B18 的改动区域不重叠——两批谁先谁后都不影响结果，见各卡内的"共享文件"提示。
- **登录无限流**（findings.md「user 模块 §6.1」#6）→ `S4-config.md`（B19，CFG-1）。该卡只给 `UserController.login` 加一个 `@RateLimit` 注解和一行 import（方法体/参数列表/返回类型一律不动），不新建任何测试文件，也不依赖本批 USER-6 新增的 `TestSecurityConfig`——本批不需要为 B19 预留任何东西。
- **任何影子事件类迁移** → `S2-events.md`（B13/B16）。user 模块不发布也不监听任何本地事件，与该模式无交集。

---

### USER-1 | 注册后状态直接 ACTIVE，从不生成激活令牌（PUB-001 根因）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserRegisterService.java`
  2. `code/ecommerce-user/src/test/java/com/ecommerce/user/service/UserRegisterServiceTest.java`
- **现状**: `register()`（约第43-77行）第57行 `user.setStatus(UserStatus.ACTIVE);`——用户一注册就是可登录状态，完全跳过邮箱激活环节；全程没有创建任何 `EmailActivationToken`；发的欢迎通知模板码是 `"WELCOME"`、变量只有 `nickname`，不含激活令牌。

  注意：`UserStatus.PENDING_ACTIVATION` 这个枚举值、`EmailActivationToken` 实体（字段 `userId`/`token`/`expiresAt`/`used` 齐全）、`EmailActivationTokenRepository`（`findByToken(String)`）**在基线里都已经存在且字段完整**（分别在 `code/ecommerce-user/src/main/java/com/ecommerce/user/entity/UserStatus.java`、`entity/EmailActivationToken.java`、`repository/EmailActivationTokenRepository.java`），不需要新建/改动，只是 `UserRegisterService` 从未使用它们。
- **期望**: 注册流程必须是「保存用户（状态 `PENDING_ACTIVATION`）→ 生成邮箱激活令牌 → 通过 `LocalNotificationService` 发送激活邮件」，用户点击激活链接后状态才变 `ACTIVE`。依据: `design-docs/04-用户服务设计.md` §3（注册流程）+ `design-docs/附录C-数据模型.md` users.status 枚举 + README.md §8.1 PUB-001（"注册→PENDING_ACTIVATION，激活→ACTIVE，登录返回 JWT"）。
- **改法**: `UserRegisterService.java` 整个文件替换为（构造函数新增 `EmailActivationTokenRepository` 依赖；`register()` 里 `setStatus` 改 `PENDING_ACTIVATION`，`save` 之后生成并持久化 24 小时有效期的激活令牌，通知模板与变量同步更新）：

  ```java
  package com.ecommerce.user.service;

  import com.ecommerce.common.exception.ConflictException;
  import com.ecommerce.common.notification.LocalNotificationService;
  import com.ecommerce.common.notification.NotificationChannel;
  import com.ecommerce.common.notification.NotificationRequest;
  import com.ecommerce.user.dto.RegisterRequest;
  import com.ecommerce.user.dto.UserResponse;
  import com.ecommerce.user.entity.EmailActivationToken;
  import com.ecommerce.user.entity.User;
  import com.ecommerce.user.entity.UserRole;
  import com.ecommerce.user.entity.UserStatus;
  import com.ecommerce.user.repository.EmailActivationTokenRepository;
  import com.ecommerce.user.repository.UserRepository;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;

  import java.time.LocalDateTime;
  import java.util.HashMap;
  import java.util.Map;
  import java.util.UUID;

  /**
   * Handles user registration.
   */
  @Service
  public class UserRegisterService {

      private static final Logger log = LoggerFactory.getLogger(UserRegisterService.class);

      private final UserRepository userRepository;
      private final BCryptPasswordEncoder passwordEncoder;
      private final LocalNotificationService notificationService;
      private final EmailActivationTokenRepository activationTokenRepository;

      public UserRegisterService(UserRepository userRepository,
                                 BCryptPasswordEncoder passwordEncoder,
                                 LocalNotificationService notificationService,
                                 EmailActivationTokenRepository activationTokenRepository) {
          this.userRepository = userRepository;
          this.passwordEncoder = passwordEncoder;
          this.notificationService = notificationService;
          this.activationTokenRepository = activationTokenRepository;
      }

      @Transactional
      public UserResponse register(RegisterRequest request) {
          // Check uniqueness
          if (userRepository.existsByEmail(request.getEmail())) {
              throw new ConflictException("Email already registered: " + request.getEmail());
          }
          if (userRepository.existsByPhone(request.getPhone())) {
              throw new ConflictException("Phone already registered: " + request.getPhone());
          }

          User user = new User();
          user.setEmail(request.getEmail());
          user.setPhone(request.getPhone());
          user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
          user.setNickname(request.getNickname());
          user.setStatus(UserStatus.PENDING_ACTIVATION);
          user.setRole(UserRole.USER);

          User saved = userRepository.save(user);
          log.info("User registered: id={}, email={}, status={}", saved.getId(), saved.getEmail(), saved.getStatus());

          EmailActivationToken activationToken = new EmailActivationToken();
          activationToken.setUserId(saved.getId());
          activationToken.setToken(UUID.randomUUID().toString());
          activationToken.setExpiresAt(LocalDateTime.now().plusHours(24));
          activationToken.setUsed(false);
          activationTokenRepository.save(activationToken);

          // Send activation email via LocalNotificationService
          NotificationRequest notification = new NotificationRequest();
          notification.setBizType("USER_REGISTER");
          notification.setBizId(String.valueOf(saved.getId()));
          notification.setReceiver(saved.getEmail());
          notification.setChannel(NotificationChannel.EMAIL);
          notification.setTemplateCode("activation_email");
          Map<String, Object> variables = new HashMap<>();
          variables.put("nickname", saved.getNickname());
          variables.put("activationToken", activationToken.getToken());
          notification.setVariables(variables);
          notificationService.send(notification);

          return UserResponse.from(saved);
      }
  }
  ```

  不要碰 `UserController.java`——它已经原样透传 `userRegisterService.register(request)` 的返回值并用 `HttpStatus.CREATED`，不需要改；也**不要**给 `UserResponse`/`RegisterRequest` 加 `activationToken` 字段（见下方"验收"说明为什么不需要，且 README.md §附录A §2.1 冻结的 201 响应体只有 `userId`/`email`/`status` 三个字段，多加字段没有必要）。

  同步替换 `UserRegisterServiceTest.java` 整个文件为（新增 `activationTokenRepository` mock、4 处既有断言把 `ACTIVE` 改 `PENDING_ACTIVATION`、通知断言把模板码/变量改成新值、新增一个校验令牌落库的测试方法）：

  ```java
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
  ```

- **验收**:
  1. `mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-user -am` → `UserRegisterServiceTest` 6/6 绿。
  2. `mvn -s maven-settings.xml -f code/pom.xml install -DskipTests` 后跑 `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub001_registerActivateLogin test`：黑盒 fixture（`test-cases/.../fixture/UserFixture.java` 的 `parseRegisterResult`）**先**尝试从注册响应体读 `activationToken` 字段（读不到，因为响应体按契约只有 `userId`/`email`/`status`），读不到就**自动回退**到 `BlackboxHarnessConfig.findActivationTokenForUser(userId)`——这个方法直接注入 `EmailActivationTokenRepository` 按 `userId` 过滤 `findAll()` 取未使用的令牌。只要本卡把令牌真正 `save()` 进这个 repository，回退路径就能拿到值，PUB-001 断言 `regResult.getStatus()=="PENDING_ACTIVATION"` 且 `regResult.getActivationToken()` 非空、随后激活/登录/查询自身信息全部 200 即可通过。**不需要**也不应该修改注册响应体去暴露该字段。
  3. `grep -rn "UserStatus.ACTIVE" code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserRegisterService.java` 零命中（确认没有遗留旧状态赋值）。

---

### USER-2 | `login()` 对 USER_FROZEN/USER_NOT_ACTIVE 抛 400 而非 403（PUB-105 根因）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserAuthService.java`（**只改 `login()` 方法体的 2 行 throw 语句**）
  2. `code/ecommerce-user/src/test/java/com/ecommerce/user/service/UserAuthServiceTest.java`（**只改 2 个 login 相关测试方法**）
- **现状**: `UserAuthService.login()` 第57-85行中，第61-66行状态校验块：
  ```java
          if (user.getStatus() != UserStatus.ACTIVE) {
              if (user.getStatus() == UserStatus.FROZEN) {
                  throw new BusinessException("USER_FROZEN", "Account is frozen: " + user.getEmail());
              }
              throw new BusinessException("USER_NOT_ACTIVE", "Account is not active: " + user.getEmail());
          }
  ```
  `BusinessException` 经 `GlobalExceptionHandler.handleBusiness(...)` 统一映射 HTTP 400（固定，不看 code）；而 README.md §7.2 业务错误码表把 `USER_NOT_ACTIVE`、`USER_FROZEN` 都定义为 **403**。同一文件第69行密码错误分支已经正确用了 `AuthorizationException("UNAUTHORIZED", ...)`——`GlobalExceptionHandler.handleAuthorization(...)` 对 `AuthorizationException` 按 `code` 分流：`code=="UNAUTHORIZED"` → 401，其余任何 code（含 `USER_FROZEN`/`USER_NOT_ACTIVE`）→ 403，这正是本卡需要复用的既有机制。
- **期望**: 未激活/已冻结用户登录，返回 403 + `code=USER_NOT_ACTIVE` 或 `code=USER_FROZEN`。依据: `design-docs/03-通用规范与非功能设计.md` §2（`AuthorizationException`=401/403，`BusinessException`=400 恒定）+ README.md §7.2 + README.md §8.2 PUB-105（"未激活不可登录｜HTTP 403，code=USER_NOT_ACTIVE"）。
- **改法**: 把上面那 5 行里的两处 `BusinessException` 换成 `AuthorizationException`（构造参数不变，`AuthorizationException` 已经在文件顶部被 import，不需要加/删 import）：

  ```java
          if (user.getStatus() != UserStatus.ACTIVE) {
              if (user.getStatus() == UserStatus.FROZEN) {
                  throw new AuthorizationException("USER_FROZEN", "Account is frozen: " + user.getEmail());
              }
              throw new AuthorizationException("USER_NOT_ACTIVE", "Account is not active: " + user.getEmail());
          }
  ```

  改完后检查：文件顶部 `import com.ecommerce.common.exception.BusinessException;` 这一行——如果 USER-5（同一文件，改 `activate()` 的另外 2 处 `BusinessException`）已经应用，`BusinessException` 在全文件已无引用，一并删掉这行 import；如果 USER-5 还没应用，`activate()` 里还在用，先保留，不影响编译（未使用 import 在本项目不是编译错误，最多是 IDE 提示）。

  **共享文件提示**：`UserAuthService.java` 同时被本卡、USER-5、以及 `S3-audit.md`（B18，改 `freezeUser`/`unfreezeUser` 签名和构造函数）三张卡编辑，三者改动区域互不重叠（本卡只动 `login()` 里的 2 行 throw），任意顺序应用都不冲突。**不要**顺手改 `activate()`（USER-5 的地盘）或 `freezeUser`/`unfreezeUser`/构造函数（B18 的地盘）。

  同步修改 `UserAuthServiceTest.java` 里两个测试方法（其余测试、mock 字段、`@InjectMocks` 不动）：

  原（约第100-124行）:
  ```java
      @Test
      @DisplayName("rejects login when user account is FROZEN")
      void testLogin_userNotActive_throwsException() {
          User frozenUser = activeUser();
          frozenUser.setStatus(UserStatus.FROZEN);
          LoginRequest request = loginRequest("active@example.com", "correctPassword");

          when(userRepository.findByEmail("active@example.com")).thenReturn(Optional.of(frozenUser));

          assertThatThrownBy(() -> userAuthService.login(request))
                  .isInstanceOf(BusinessException.class)
                  .hasMessageContaining("Account is frozen");
      }

      @Test
      @DisplayName("rejects login when user account status is not ACTIVE (non-FROZEN)")
      void testLogin_pendingActivationStatus_throwsException() {
          User pendingUser = activeUser();
          pendingUser.setStatus(UserStatus.PENDING_ACTIVATION);
          LoginRequest request = loginRequest("active@example.com", "correctPassword");

          when(userRepository.findByEmail("active@example.com")).thenReturn(Optional.of(pendingUser));

          assertThatThrownBy(() -> userAuthService.login(request))
                  .isInstanceOf(BusinessException.class)
                  .hasMessageContaining("Account is not active");
      }
  ```

  改为:
  ```java
      @Test
      @DisplayName("rejects login with 403 AuthorizationException(USER_FROZEN) when user account is FROZEN")
      void testLogin_userNotActive_throwsException() {
          User frozenUser = activeUser();
          frozenUser.setStatus(UserStatus.FROZEN);
          LoginRequest request = loginRequest("active@example.com", "correctPassword");

          when(userRepository.findByEmail("active@example.com")).thenReturn(Optional.of(frozenUser));

          assertThatThrownBy(() -> userAuthService.login(request))
                  .isInstanceOf(AuthorizationException.class)
                  .hasMessageContaining("Account is frozen");
      }

      @Test
      @DisplayName("rejects login with 403 AuthorizationException(USER_NOT_ACTIVE) when status is not ACTIVE (non-FROZEN)")
      void testLogin_pendingActivationStatus_throwsException() {
          User pendingUser = activeUser();
          pendingUser.setStatus(UserStatus.PENDING_ACTIVATION);
          LoginRequest request = loginRequest("active@example.com", "correctPassword");

          when(userRepository.findByEmail("active@example.com")).thenReturn(Optional.of(pendingUser));

          assertThatThrownBy(() -> userAuthService.login(request))
                  .isInstanceOf(AuthorizationException.class)
                  .hasMessageContaining("Account is not active");
      }
  ```

  `AuthorizationException` 已在测试文件顶部 import，不需要新增；`BusinessException` import 的去留判断同主文件（等 USER-5 的 2 处也改完再删）。
- **验收**:
  1. `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub105_unactivatedUserCannotLogin test` → 绿（响应 403，`$.code`="USER_NOT_ACTIVE"）。
  2. `UserAuthServiceTest` 里两个 login 测试断言 `AuthorizationException` 通过。
  3. FROZEN 分支没有独立公开黑盒用例覆盖，靠 `UserAuthServiceTest.testLogin_userNotActive_throwsException` 单测把关；若想端到端确认，可用已冻结用户走 `/api/v1/users/login`，断言 403 + `code=USER_FROZEN`。

---

### USER-3 | `AddressFormatter.format()` 参数顺序颠倒

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/AddressFormatter.java`
  2. `code/ecommerce-user/src/test/java/com/ecommerce/user/service/AddressFormatterTest.java`
- **现状**: 第20行方法签名 `public String format(String city, String province, String district, String detail)`——第一个形参叫 `city`，第二个叫 `province`；但第21行方法体 `return province + city + district + detail;` 是按**变量名**拼接。`design-docs/04-用户服务设计.md` §5 冻结的签名是 `format(String province, String city, String district, String detail)`（province 在前）。

  这个方法目前是**死代码**（`grep -rn "AddressFormatter" code/` 只命中它自己的类和自己的测试，`AddressService` 创建/更新地址时完全没有调用它），所以现在还没有任何真实调用点被这个参数顺序坑到。但基线的 `AddressFormatterTest.java` 本身就是按"当前（错误）参数顺序"故意调用来让测试保持绿色的——例如 `addressFormatter.format("杭州", "浙江", "西湖区", "文三路478号")`（city 在前）才能得到期望输出 `"浙江杭州西湖区文三路478号"`；如果真按文档要求的 `(province, city, ...)` 顺序调用，即 `format("浙江", "杭州", ...)`，第一实参"浙江"会落进名叫 `city` 的形参、第二实参"杭州"落进名叫 `province` 的形参，body 里 `province + city + ...` 就会输出 `"杭州浙江..."`——省市颠倒。
- **期望**: 方法签名必须是 `format(String province, String city, String district, String detail)`，"参数顺序不得调整"。依据: `design-docs/04-用户服务设计.md` §5。
- **改法**: 只调整形参声明顺序（`city`/`province` 互换位置）和对应的 javadoc `@param` 顺序，方法体 `return` 语句一个字符都不用改（它本来就是按 `province + city + district + detail` 拼接，只是之前绑错了形参名）：

  ```java
  package com.ecommerce.user.service;

  import org.springframework.stereotype.Service;

  /**
   * Formats a Chinese address into a single string.
   */
  @Service
  public class AddressFormatter {

      /**
       * Formats address components into: province + city + district + detail.
       *
       * @param province the province
       * @param city     the city
       * @param district the district/county
       * @param detail   the street / building / doorplate detail
       * @return the formatted full address string
       */
      public String format(String province, String city, String district, String detail) {
          return province + city + district + detail;
      }
  }
  ```

  由于是死代码，不需要去别处找调用点改参数传递顺序；但必须同步改测试的调用顺序（否则测试会按旧的错误顺序调用，编译能过，断言会失败），`AddressFormatterTest.java` 整个文件替换为：

  ```java
  package com.ecommerce.user.service;

  import org.junit.jupiter.api.DisplayName;
  import org.junit.jupiter.api.Test;

  import static org.assertj.core.api.Assertions.assertThat;

  @DisplayName("AddressFormatter")
  class AddressFormatterTest {

      private final AddressFormatter addressFormatter = new AddressFormatter();

      /**
       * The format() signature is (province, city, district, detail), matching
       * design-docs/04 section 5. Callers must pass values in that order.
       */
      @Test
      @DisplayName("formats address with correct output order province+city+district+detail")
      void testFormat_combinesProvinceCityDistrictDetail() {
          String result = addressFormatter.format("浙江", "杭州", "西湖区", "文三路478号");

          assertThat(result).isEqualTo("浙江杭州西湖区文三路478号");
      }

      @Test
      @DisplayName("formats address without detail when detail is empty")
      void testFormat_emptyDetail_omitsDetail() {
          String result = addressFormatter.format("广东", "深圳", "南山区", "");

          assertThat(result).isEqualTo("广东深圳南山区");
      }

      @Test
      @DisplayName("formats address with all components concatenated without separators")
      void testFormat_noDelimitersBetweenComponents() {
          String result = addressFormatter.format("四川", "成都", "高新区", "天府大道999号");

          assertThat(result).isEqualTo("四川成都高新区天府大道999号");
      }
  }
  ```

- **验收**:
  1. `mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-user -am -Dtest=AddressFormatterTest test` 3/3 绿。
  2. 手工验证：`new AddressFormatter().format("浙江", "杭州", "西湖区", "文三路478号")` 必须等于 `"浙江杭州西湖区文三路478号"`（province 作为**第一个实参**传入）。
  3. `grep -rn "\.format(" code/ecommerce-user/src/main` 确认除 `AddressFormatter` 类自身声明外没有其他调用点（若未来有人接入调用，务必按 `(province, city, district, detail)` 顺序传参）。

---

### USER-4 | 地址 `isDefault` 的 JSON key 被 Jackson 静默改名为 `default`

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/dto/AddressRequest.java`
  2. `code/ecommerce-user/src/main/java/com/ecommerce/user/dto/AddressResponse.java`
  3. `code/ecommerce-user/src/test/java/com/ecommerce/user/dto/AddressRequestJsonTest.java` 【新增，推荐一并加，纯新增不影响任何现有代码】
  4. `code/ecommerce-user/src/test/java/com/ecommerce/user/dto/AddressResponseJsonTest.java` 【新增，推荐一并加，纯新增不影响任何现有代码】
- **现状**: 两个 DTO 都只有裸的 `isDefault()`/`setDefault(boolean)` 存取器对（`AddressRequest.java` 字段第28行、getter 第81行、setter 第85行；`AddressResponse.java` 字段第17行、getter 第91行、setter 第95行），没有任何 `@JsonProperty` 注解。Jackson 按 JavaBean 内省约定推断属性名：`isDefault()` 去掉 `is` 前缀、首字母小写 → `default`；`setDefault(boolean)` 去掉 `set` 前缀、首字母小写 → `default`——两者一致推出 JSON 属性名是 `"default"`，不是 `"isDefault"`。

  仓库全局搜索未发现任何 `spring.jackson.deserialization.fail-on-unknown-properties` 配置，走 Spring Boot 默认值 `false`，即未识别字段**静默丢弃、不报错**。后果两个方向都错：
  - 反序列化：客户端 `POST /api/v1/users/addresses` 请求体里的 `"isDefault": true` 因为不是 Jackson 认识的属性名而被静默忽略，`request.isDefault()` 永远拿到字段默认值 `false`，不管客户端传的是什么。
  - 序列化：`GET /api/v1/users/addresses` 等接口返回的 JSON 里这个字段的 key 实际是 `"default"`，不是契约要求的 `"isDefault"`，任何按字面 key 读取的客户端/断言都读不到值。

  黑盒测试 fixture `test-cases/src/test/java/com/ecommerce/blackbox/common/fixture/UserFixture.java` 第138行 `body.put("isDefault", true);`——公开黑盒 fixture 构造请求体时字面用的就是 `"isDefault"` 这个 key，是这个契约字段名最直接的证据（`design-docs/附录C-数据模型.md` 的 `user_addresses.default_address` 只是数据库列名，与 REST JSON 字段名没有必然对应关系，不能作为 JSON key 的依据）。24 个公开用例里的 PUB-002 没有断言 `isDefault` 回显，所以这个 bug 不会导致公开用例失败，但符合"不要只盯着可见用例"的修复方向——隐藏用例大概率会断言它。
- **期望**: 请求体和响应体里这个字段的 JSON key 都必须字面是 `"isDefault"`。依据: README.md（冻结契约下字段名不可静默改变）+ `test-cases/.../fixture/UserFixture.java:138`（黑盒 fixture 实测用的字面 key）。
- **改法**: 两个 DTO 的 getter 和 setter 都加 `@JsonProperty("isDefault")`（getter/setter 都要加，两个都不能漏——只加一个的话，Jackson 仍会用另一个未标注的存取器的默认推断名，读写方向会不一致）：

  `AddressRequest.java`——顶部加 import，第81行/第85行两处方法签名各自加注解:
  ```java
  import com.fasterxml.jackson.annotation.JsonProperty;
  import jakarta.validation.constraints.NotBlank;
  ```
  ```java
      @JsonProperty("isDefault")
      public boolean isDefault() {
          return isDefault;
      }

      @JsonProperty("isDefault")
      public void setDefault(boolean isDefault) {
          this.isDefault = isDefault;
      }
  ```

  `AddressResponse.java`——顶部加 import，第91行/第95行两处方法签名各自加注解:
  ```java
  import com.ecommerce.user.entity.UserAddress;
  import com.fasterxml.jackson.annotation.JsonProperty;
  ```
  ```java
      @JsonProperty("isDefault")
      public boolean isDefault() {
          return isDefault;
      }

      @JsonProperty("isDefault")
      public void setDefault(boolean isDefault) {
          this.isDefault = isDefault;
      }
  ```

  其余字段（`province`/`city`/`district`/`detail`/`receiverName`/`receiverPhone`/`addressId`）、`AddressResponse.from(UserAddress)` 静态工厂方法体都不用动——它们调 `address.isDefault()`/`response.setDefault(...)` 是纯 Java 方法调用，不经过 Jackson，不受影响。

  可选新增两个纯 pinning 测试类（与 kb 一致，零冲突风险，直接复制）：

  `code/ecommerce-user/src/test/java/com/ecommerce/user/dto/AddressRequestJsonTest.java`:
  ```java
  package com.ecommerce.user.dto;

  import com.fasterxml.jackson.databind.ObjectMapper;
  import org.junit.jupiter.api.Test;

  import static org.junit.jupiter.api.Assertions.assertEquals;
  import static org.junit.jupiter.api.Assertions.assertTrue;

  /**
   * Pins the corrected JSON field naming for {@link AddressRequest#isDefault}
   * (design-implementation fix: the black-box fixture posts the literal key
   * "isDefault", but a bare {@code isDefault()}/{@code setDefault()} pair
   * would have Jackson infer the property name "default" instead).
   */
  class AddressRequestJsonTest {

      @Test
      void isDefault_deserializesFromJsonKeyIsDefault() throws Exception {
          ObjectMapper mapper = new ObjectMapper();
          String json = "{\"province\":\"Guangdong\",\"city\":\"Shenzhen\","
                  + "\"district\":\"Nanshan\",\"detail\":\"No.1\",\"isDefault\":true}";

          AddressRequest request = mapper.readValue(json, AddressRequest.class);

          assertTrue(request.isDefault());
      }

      @Test
      void isDefault_serializesToJsonKeyIsDefault() throws Exception {
          ObjectMapper mapper = new ObjectMapper();
          AddressRequest request = new AddressRequest();
          request.setDefault(true);

          String json = mapper.writeValueAsString(request);

          assertTrue(json.contains("\"isDefault\":true"));
      }

      @Test
      void isDefault_doesNotSerializeAsBareDefault() throws Exception {
          ObjectMapper mapper = new ObjectMapper();
          AddressRequest request = new AddressRequest();
          request.setDefault(true);

          String json = mapper.writeValueAsString(request);

          assertEquals(false, json.contains("\"default\":true"));
      }
  }
  ```

  `code/ecommerce-user/src/test/java/com/ecommerce/user/dto/AddressResponseJsonTest.java`:
  ```java
  package com.ecommerce.user.dto;

  import com.fasterxml.jackson.databind.ObjectMapper;
  import org.junit.jupiter.api.Test;

  import static org.junit.jupiter.api.Assertions.assertTrue;

  /**
   * Pins the corrected JSON field naming for {@link AddressResponse#isDefault},
   * mirroring {@link AddressRequestJsonTest}: responses returned to black-box
   * clients must expose the boolean under the literal key "isDefault".
   */
  class AddressResponseJsonTest {

      @Test
      void isDefault_serializesToJsonKeyIsDefault() throws Exception {
          ObjectMapper mapper = new ObjectMapper();
          AddressResponse response = new AddressResponse();
          response.setDefault(true);

          String json = mapper.writeValueAsString(response);

          assertTrue(json.contains("\"isDefault\":true"));
      }

      @Test
      void isDefault_deserializesFromJsonKeyIsDefault() throws Exception {
          ObjectMapper mapper = new ObjectMapper();
          String json = "{\"addressId\":1,\"province\":\"Guangdong\",\"city\":\"Shenzhen\","
                  + "\"district\":\"Nanshan\",\"detail\":\"No.1\",\"isDefault\":true}";

          AddressResponse response = mapper.readValue(json, AddressResponse.class);

          assertTrue(response.isDefault());
      }
  }
  ```

- **验收**:
  1. `new ObjectMapper().readValue("{\"province\":\"浙江\",\"city\":\"杭州\",\"district\":\"西湖区\",\"detail\":\"x\",\"isDefault\":true}", AddressRequest.class).isDefault()` == `true`。
  2. `new ObjectMapper().writeValueAsString(addressResponseWithDefaultTrue)` 包含子串 `"isDefault":true`，不包含 `"default":true`。
  3. 若新增了两个 pinning 测试类：`mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-user -am -Dtest=AddressRequestJsonTest,AddressResponseJsonTest test` 全绿。
  4. 端到端：`POST /api/v1/users/addresses` 请求体带 `"isDefault": true`，响应体（201）里必须能看到字面 `"isDefault":true`（而不是 `"default":true`）。

---

### USER-5 | `activate()` 对已用/已过期令牌抛 400，应为 409

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserAuthService.java`（**只改 `activate()` 方法体的 2 行 throw 语句 + import**）
  2. `code/ecommerce-user/src/test/java/com/ecommerce/user/service/UserAuthServiceTest.java`（**只改 2 个 activate 相关测试方法 + import**）
- **现状**: `activate()`（约第91-108行）第95-101行：
  ```java
          if (activationToken.isUsed()) {
              throw new BusinessException("CONFLICT", "Activation token has already been used");
          }

          if (activationToken.getExpiresAt().isBefore(LocalDateTime.now())) {
              throw new BusinessException("CONFLICT", "Activation token has expired");
          }
  ```
  同 USER-2 的根因：`BusinessException` 恒映射 400，而这两种情形本质是"状态冲突/重复提交"，README.md §7.1 通用错误码表把 `CONFLICT` 定义为 409。
- **期望**: 已使用或已过期的激活令牌应返回 409。依据: `design-docs/03-通用规范与非功能设计.md` §2（`ConflictException`=409）+ README.md §7.1（`CONFLICT | 409 | 状态冲突或重复请求`）。这里没有专属的激活令牌错误码（不是 `USER_NOT_ACTIVE`/`USER_FROZEN` 那种业务错误码表里单列的码），用通用 `CONFLICT` 码即可——`ConflictException` 单参构造函数内部固定 `code=CONFLICT`（`code/ecommerce-common/src/main/java/com/ecommerce/common/exception/ConflictException.java` 第11-13行 `public ConflictException(String message) { super(CODE, message); }`，`CODE` 常量即 `"CONFLICT"`），这个构造函数**在基线里已经存在**，不需要改 `ecommerce-common`。
- **改法**: 把上面 2 处 `BusinessException` 换成 `ConflictException`（只传 message，不传 code——用现成的单参构造函数）：

  ```java
          if (activationToken.isUsed()) {
              throw new ConflictException("Activation token has already been used");
          }

          if (activationToken.getExpiresAt().isBefore(LocalDateTime.now())) {
              throw new ConflictException("Activation token has expired");
          }
  ```

  文件顶部 import 区加一行 `import com.ecommerce.common.exception.ConflictException;`（按字母序插在 `AuthorizationException` 和 `ResourceNotFoundException` 之间）：
  ```java
  import com.ecommerce.common.exception.AuthorizationException;
  import com.ecommerce.common.exception.ConflictException;
  import com.ecommerce.common.exception.ResourceNotFoundException;
  ```
  `import com.ecommerce.common.exception.BusinessException;` 的去留判断与 USER-2 一致：改完这 2 处后，如果 USER-2 的 2 处也已经改完，`BusinessException` 全文件无引用，删掉该行；如果 USER-2 还没应用（`login()` 里还在用），先保留。

  **共享文件提示**：与 USER-2 一样，`UserAuthService.java` 也被 `S3-audit.md`（B18）编辑（`freezeUser`/`unfreezeUser`/构造函数），本卡改动区域（`activate()` 方法体）与之不重叠，不要越界。

  同步修改 `UserAuthServiceTest.java` 顶部 import 加 `import com.ecommerce.common.exception.ConflictException;`，两个测试方法（约第184-224行）：

  原:
  ```java
      @Test
      @DisplayName("throws exception when activation token is already used")
      void testActivate_alreadyUsedToken_throwsException() {
          ActivateRequest activateRequest = new ActivateRequest();
          activateRequest.setToken("used-token");

          EmailActivationToken usedToken = new EmailActivationToken();
          usedToken.setUserId(1L);
          usedToken.setToken("used-token");
          usedToken.setExpiresAt(LocalDateTime.now().plusHours(24));
          usedToken.setUsed(true);

          when(activationTokenRepository.findByToken("used-token"))
                  .thenReturn(Optional.of(usedToken));

          assertThatThrownBy(() -> userAuthService.activate(activateRequest))
                  .isInstanceOf(BusinessException.class)
                  .hasMessageContaining("already been used");
      }

      @Test
      @DisplayName("throws exception when activation token is expired")
      void testActivate_expiredToken_throwsException() {
          ActivateRequest activateRequest = new ActivateRequest();
          activateRequest.setToken("expired-token");

          EmailActivationToken expiredToken = new EmailActivationToken();
          expiredToken.setUserId(1L);
          expiredToken.setToken("expired-token");
          expiredToken.setExpiresAt(LocalDateTime.now().minusHours(1));
          expiredToken.setUsed(false);

          when(activationTokenRepository.findByToken("expired-token"))
                  .thenReturn(Optional.of(expiredToken));

          assertThatThrownBy(() -> userAuthService.activate(activateRequest))
                  .isInstanceOf(BusinessException.class)
                  .hasMessageContaining("expired");
      }
  ```

  改为:
  ```java
      @Test
      @DisplayName("throws 409 ConflictException when activation token is already used")
      void testActivate_alreadyUsedToken_throwsException() {
          ActivateRequest activateRequest = new ActivateRequest();
          activateRequest.setToken("used-token");

          EmailActivationToken usedToken = new EmailActivationToken();
          usedToken.setUserId(1L);
          usedToken.setToken("used-token");
          usedToken.setExpiresAt(LocalDateTime.now().plusHours(24));
          usedToken.setUsed(true);

          when(activationTokenRepository.findByToken("used-token"))
                  .thenReturn(Optional.of(usedToken));

          assertThatThrownBy(() -> userAuthService.activate(activateRequest))
                  .isInstanceOf(ConflictException.class)
                  .hasMessageContaining("already been used");
      }

      @Test
      @DisplayName("throws 409 ConflictException when activation token is expired")
      void testActivate_expiredToken_throwsException() {
          ActivateRequest activateRequest = new ActivateRequest();
          activateRequest.setToken("expired-token");

          EmailActivationToken expiredToken = new EmailActivationToken();
          expiredToken.setUserId(1L);
          expiredToken.setToken("expired-token");
          expiredToken.setExpiresAt(LocalDateTime.now().minusHours(1));
          expiredToken.setUsed(false);

          when(activationTokenRepository.findByToken("expired-token"))
                  .thenReturn(Optional.of(expiredToken));

          assertThatThrownBy(() -> userAuthService.activate(activateRequest))
                  .isInstanceOf(ConflictException.class)
                  .hasMessageContaining("expired");
      }
  ```

- **验收**:
  1. `UserAuthServiceTest` 里这两个 activate 测试断言 `ConflictException` 通过。
  2. 24 个公开黑盒用例没有直接覆盖"重复/过期激活"场景，靠上面的单测把关；端到端可手工验证：先激活一个令牌成功一次，再用同一个 `token` 调 `POST /api/v1/users/activate` 第二次，应返回 409（不是 400）。
  3. `grep -rn "BusinessException" code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserAuthService.java` 在 USER-2 与本卡都应用后应为 0 命中（import 已清理，`freezeUser`/`unfreezeUser` 从不抛 `BusinessException`）。

---

### USER-6 | user 模块与 app 模块两份 `SecurityFilterChain` 并存

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/config/SecurityConfig.java`（大幅精简：删 `SecurityFilterChain` bean + `@EnableWebSecurity`，只留 `BCryptPasswordEncoder` bean）
  2. `code/ecommerce-user/src/test/java/com/ecommerce/user/config/TestSecurityConfig.java` 【新增】（`config` 这个测试子包在基线里不存在，需要新建目录）
  3. `code/ecommerce-user/src/test/java/com/ecommerce/user/controller/UserControllerTest.java`（只改 1 处 import + 1 处 `@Import` 注解内容）
  4. `code/ecommerce-user/src/test/java/com/ecommerce/user/controller/AdminUserControllerTest.java`（**只改** 1 处 import + 1 处 `@Import` 注解内容；文件里 `verify(userAuthService).freezeUser(5L)`/`unfreezeUser(5L)` 那两行**不要动**，属 `S3-audit.md`/B18 的地盘）
  5. `code/ecommerce-user/src/test/java/com/ecommerce/user/controller/AddressControllerTest.java`（只改 1 处 import + 1 处 `@Import` 注解内容）
- **现状**: `ecommerce-user` 和 `ecommerce-app` 各自定义了一份完整的 `@Configuration` + `@EnableWebSecurity` + `SecurityFilterChain` bean：
  - `code/ecommerce-user/src/main/java/com/ecommerce/user/config/SecurityConfig.java`（无 bean 名限定，`authorizeHttpRequests` 规则集是 app 那份的一个不完整子集——比如没有 `/api/v1/payment/callback`、`/api/v1/logistics/callback`、`/api/v1/admin/system/**` 这些 permitAll 规则，catch-all 是 `.anyRequest().authenticated()`）。
  - `code/ecommerce-app/src/main/java/com/ecommerce/app/SecurityConfig.java`（`@Configuration("appSecurityConfig")`、bean 名 `appSecurityFilterChain`，规则集更完整，catch-all 是 `hasRole("USER")` + `anyRequest().permitAll()`）。

  由于 `ShopHubApplication` 的组件扫描会同时扫到 `com.ecommerce.user.config.SecurityConfig` 和 `com.ecommerce.app.SecurityConfig`，两个 `SecurityFilterChain` bean 都会被注册到 Spring Security 的 `FilterChainProxy`。两者都没有 `securityMatcher()`/`@Order`，默认都"匹配所有请求"，`FilterChainProxy` 实际生效哪一条完全取决于 bean **注册顺序**（Spring 内部由 `@ComponentScan` 扫描顺序 + bean 定义处理顺序决定，没有任何显式契约保证），任何依赖版本、classpath 顺序、模块编译顺序的变化都可能让"谁生效"静默反转——这是脆弱的隐藏耦合，不是当前必现的 24 例失败，但违反了设计上"安全配置全局唯一、由 app-bootstrap 持有"的意图。
- **期望**: 全应用只应该有一份权威 `SecurityFilterChain`，由 `ecommerce-app` 持有；`ecommerce-user` 只保留业务代码需要按具体类型直接注入的 `BCryptPasswordEncoder` bean。依据: `design-docs/02-系统架构.md` §2（模块依赖图——`app-bootstrap` 位于顶层，依赖并统领所有业务模块）+ CLAUDE.md 模块职责表（`ecommerce-app` 一栏明确写着"Spring Security 配置"是其职责）。
- **改法**:

  **1) `code/ecommerce-user/src/main/java/com/ecommerce/user/config/SecurityConfig.java`** 整个文件替换为：
  ```java
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
  ```
  注意：这个类**不能删掉**，只是删掉 `@EnableWebSecurity` 注解和 `securityFilterChain(...)` 这个 `@Bean` 方法（连带不再需要的 `JwtAuthFilter`/`JwtTokenProvider`/`HttpSecurity`/`SessionCreationPolicy`/`SecurityFilterChain`/`UsernamePasswordAuthenticationFilter` 相关 import 和构造函数），`@Configuration` + `BCryptPasswordEncoder` 这个 bean 必须留着。

  **2) 新建 `code/ecommerce-user/src/test/java/com/ecommerce/user/config/TestSecurityConfig.java`**（`ecommerce-user` 的 `pom.xml` 只依赖 `ecommerce-common`，不依赖 `ecommerce-app`——依赖方向是 app→user，物理上无法在 user 模块的测试里 `@Import` app 模块的 `SecurityConfig`，所以必须新建一份模块内部、仅供 `@WebMvcTest` 切片测试使用的安全配置，规则集照抄 user 模块被删掉的那份旧 `SecurityFilterChain`）：
  ```java
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
  ```

  **3) 三个 `@WebMvcTest` 文件**——每个都只改 1 处 import + `@Import` 注解里的类名，其余全部不动：

  `UserControllerTest.java`（第11行 + 第39行）：
  ```java
  import com.ecommerce.user.config.SecurityConfig;
  ```
  →
  ```java
  import com.ecommerce.user.config.TestSecurityConfig;
  ```
  ```java
  @Import({JwtTokenProvider.class, SecurityConfig.class})
  ```
  →
  ```java
  @Import({JwtTokenProvider.class, TestSecurityConfig.class})
  ```

  `AdminUserControllerTest.java`（第3行 + 第24行，**仅此两行**，文件里两处 `verify(userAuthService).freezeUser(5L)`/`unfreezeUser(5L)` 不要碰——那是 B18 的签名变更）：
  ```java
  import com.ecommerce.user.config.SecurityConfig;
  ```
  →
  ```java
  import com.ecommerce.user.config.TestSecurityConfig;
  ```
  ```java
  @Import({JwtTokenProvider.class, SecurityConfig.class})
  ```
  →
  ```java
  @Import({JwtTokenProvider.class, TestSecurityConfig.class})
  ```

  `AddressControllerTest.java`（第5行 + 第36行）：
  ```java
  import com.ecommerce.user.config.SecurityConfig;
  ```
  →
  ```java
  import com.ecommerce.user.config.TestSecurityConfig;
  ```
  ```java
  @Import({JwtTokenProvider.class, SecurityConfig.class})
  ```
  →
  ```java
  @Import({JwtTokenProvider.class, TestSecurityConfig.class})
  ```

  **不用管的相关文件（FYI，不要动）**：
  - `S4-config.md`（B19，登录限流 CFG-1）只给 `UserController.login` 加一个 `@RateLimit` 注解和一行 import，**不新建任何测试文件**——本模块 `@WebMvcTest` 就是本卡列出的这 3 个，不存在"B19 会新建的第 4 个"，本卡不需要为 B19 预留任何东西。
  - `code/ecommerce-app/src/test/java/testsupport/DuplicateClassNameExcludeFilter.java` 里有一条 `"com.ecommerce.user.config.SecurityConfig"` 的类名排除项——这是 app 模块另一个测试专用 `@ComponentScan`（`testsupport.TestApplication`）为了避免同名类扫描冲突的既有防御机制，与本卡的 bean 冲突问题是两回事，参考实现里这个文件未出现在改动集里（说明它不需要变），不要动它。

- **验收**:
  1. `grep -c "SecurityFilterChain\|EnableWebSecurity" code/ecommerce-user/src/main/java/com/ecommerce/user/config/SecurityConfig.java` → 0；`grep -c "BCryptPasswordEncoder" 同文件` → 应 ≥ 2（import + bean 方法）。
  2. `mvn -s maven-settings.xml -f code/pom.xml install -DskipTests` 成功（确认 `ApplicationContext` 能正常装配——如果不小心删掉了 `BCryptPasswordEncoder` bean，这一步会在黑盒测试启动时报 `UnsatisfiedDependencyException`，见下方"勿犯"）。
  3. `mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-user -am` — `UserControllerTest`/`AdminUserControllerTest`/`AddressControllerTest` 全绿，尤其是每个类里"unauthenticated → 403"那几个断言（这些是真正会驱动 `TestSecurityConfig` 的 `SecurityFilterChain` 生效与否的用例——如果 `TestSecurityConfig` 没建对，`@WebMvcTest` 上下文会直接装配失败，不是断言失败而是整个测试类报错）。
  4. `mvn -s maven-settings.xml -f test-cases/pom.xml test` 24/24（回归确认——这个 bug 本身不必然导致当前 24 例失败，只是脆弱，此步是纯粹的不回归检查）。
- **勿犯**:
  1. **绝对不能删除 `BCryptPasswordEncoder` 这个 bean**，也不能把 `SecurityConfig.java` 这个文件整个删掉。`ecommerce-app` 的 `SecurityConfig` 里那个密码编码器 bean 声明的类型是接口 `PasswordEncoder`（`@Bean public PasswordEncoder passwordEncoder() {...}`），不是具体类 `BCryptPasswordEncoder`；而 `UserRegisterService`/`UserAuthService` 的构造函数按**具体类型** `BCryptPasswordEncoder` 注入。如果删掉 user 模块这个 bean，指望 app 模块的 `PasswordEncoder` bean 顶上，Spring 按类型自动装配时两者不匹配，会在应用启动阶段直接抛 `UnsatisfiedDependencyException`——不是某几个用例失败，是 **`ApplicationContext` 完全起不来，24 例全部 ERROR**，比"两份 FilterChain 并存"这个原始 bug 本身严重得多。
  2. **绝不修改 `code/ecommerce-app/src/main/java/com/ecommerce/app/SecurityConfig.java`**。那份文件同时是 `app.md`（B12）好几张卡的编辑目标（删 `reset-sandbox`/`bootstrap-admin` 的 `permitAll`、放开 `verify-purchase` 给 ADMIN、接入 `RestAuthenticationEntryPoint`/`RestAccessDeniedHandler`），本卡只负责删掉 user 模块那份重复的 `SecurityFilterChain`，不负责、也不应该改 app 模块那份"留下来的权威版本"的任何内容。
  3. **绝不加 `@EnableMethodSecurity`。** README.md §6 的全部端点已经被 URL 级安全规则 100% 覆盖，启用方法级安全不会修复任何当前可观察行为，只会让仓库里从未生效过的 `@PreAuthorize` 注解突然生效，属于纯风险无收益操作。
  4. 不要试图让 `TestSecurityConfig` 直接 `@Import` app 模块的 `SecurityConfig.class` 来"省事复用"——`ecommerce-user` 的 `pom.xml` 不依赖 `ecommerce-app`（依赖方向是 app→user），这样写根本编译不过，必须是本卡新建的这个独立类。
  5. 不要把 `AdminUserControllerTest.java` 里 `verify(userAuthService).freezeUser(5L)`/`unfreezeUser(5L)` 这两行也顺手"修好"（比如猜测性地加个 operator 参数）——那是 `S3-audit.md`（B18）的签名变更，两批各自照自己的卡改，不要越界替对方实现。
