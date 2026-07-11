# B12 · app — 安全边界 401/403 契约错误体 / 启动配置

本文件覆盖 `findings.md`「app 模块（§6.12）」全部 4 项 + 第二轮深审（§7）#2，共 **3 张卡**（APP-1..3）。
§6.12 的另外 2 项不在本文件内：#3（支付回调 `X-Payment-Signature` 头未读取/校验）findings.md 原文已注明
"根因在 payment 模块，已并入本模块回调修复"，属 payment 批（`payment.md`）范围；#4（事件失败无重放端点）
经参考实现核实 `EventFailureAdminController.java` 从未被改动——不是遗漏，是确认过的不做项（README §6.8
冻结的 9 个管理支撑端点本就不含重放，事件失败基础设施本身属事件类 S2 主题）。两项均跳过，详见本文件末尾说明。

APP-1 与 APP-3 都会改到同一个文件 `ecommerce-app/SecurityConfig.java`（APP-2 也会，改动更小）；三张卡改的是
该文件里互不重叠的三处（安全放行规则删除 / 新增一条 URL 规则 / 挂 exceptionHandling），可按任意顺序全部应用，
文件末尾附三卡合并后的完整目标内容供自查。

---

### APP-1 | reset-sandbox / bootstrap-admin 未鉴权，任何人可清库或自签 ADMIN token（安全漏洞）

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-app/src/main/java/com/ecommerce/app/controller/SystemAdminController.java`
  2. `code/ecommerce-app/src/main/java/com/ecommerce/app/SecurityConfig.java`
- **现状**: `SystemAdminController`（`@RequestMapping("/api/v1/admin/system")`）当前暴露两个端点：
  - `resetSandbox()`（第 55-95 行，`@PostMapping("/reset-sandbox")`）：反射拿到全部 `JpaRepository` bean 逐个
    `deleteAll()`，再清空 `CacheManager` 全部缓存，外加 `RuntimeConfigRegistry.clear()` /
    `SystemClockService.reset()` / `FaultInjectionRegistry.clear()` / `NotificationRecordService.clear()`——
    相当于把整个数据库和运行时测试态一键清空。
  - `bootstrapAdmin()`（第 97-127 行，`@PostMapping("/bootstrap-admin")`）：查不到 `admin@shophub.test` 就现场
    新建一个 `UserRole.ADMIN` 用户，并立即用 `JwtTokenProvider.generateToken(...)` 签发一枚 ADMIN JWT 返回给
    调用方——不对调用方做任何身份校验。

    而 `SecurityConfig.securityFilterChain()`（第 48-73 行）里第 63-64 行把这两个路径显式放行：
    ```java
    .requestMatchers("/api/v1/admin/system/reset-sandbox").permitAll()
    .requestMatchers("/api/v1/admin/system/bootstrap-admin").permitAll()
    ```
    即任何未认证请求都能直接清空全库，或者直接拿到一枚自签 ADMIN token 再去调用其余全部 `/api/v1/admin/**`
    接口——本仓库最高权限的两个后门完全不设防。这两个端点也不在 README §6.8 冻结的 9 个黑盒管理支撑端点列表
    里（该列表只有 `configs` GET/PUT、`fault-injections` POST/DELETE、`events/failures` GET、
    `notifications` GET、`clock` PUT/DELETE、`orders/timeout-cancel` POST，共 9 条）；对 `design-docs/`、
    `README.md`、`test-cases/` 全仓 grep `reset-sandbox`/`bootstrap-admin` 零命中——不是"合法端点忘了鉴权"，
    是不该存在的端点。
- **期望**: 业务代码完全不得依赖或暴露 reset/bootstrap 类接口来满足黑盒用例隔离；隔离只能由测试 harness（每
  用例全新 Spring 上下文 + 随机 H2）提供。依据: `design-docs/03-通用规范与非功能设计.md` §5（"业务代码不得
  依赖或暴露 reset/bootstrap 接口来满足黑盒用例隔离"）；`README.md` §6.8（冻结的 9 个管理支撑端点不含这两
  个）。
- **改法**:
  1. 在 `SystemAdminController.java` 里**整个删除** `resetSandbox()`（55-95 行）与 `bootstrapAdmin()`
     （97-127 行）两个方法，以及只被 `resetSandbox()` 使用的私有 helper `deletePriority(String)`（文件末尾）。
  2. 同步删除因此变成完全未使用的字段/构造参数/常量/import：`applicationContext`（`ApplicationContext`）、
     `cacheManager`（`CacheManager`）、`userRepository`（`UserRepository`）、`passwordEncoder`
     （`PasswordEncoder`）、`jwtTokenProvider`（`JwtTokenProvider`）五个字段、对应的构造函数参数、以及
     `ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_PHONE`/`ADMIN_NICKNAME` 四个常量；相应 import
     （`NotificationRecordService`、`FaultInjectionRegistry`、`User`、`UserRole`、`UserStatus`、
     `UserRepository`、`JwtTokenProvider`、`CacheManager`、`ApplicationContext`、`JpaRepository`、
     `PasswordEncoder`）一并清掉。**保留** `RuntimeConfigRegistry`、`SystemClockService`、`Logger` 相关
     import 与字段——`configs`/`clock` 四个端点原样不动。删完后类里不再需要任何依赖注入，构造函数直接消失
     （使用默认无参构造）。改完后的目标文件内容（可逐行核对）：
     ```java
     package com.ecommerce.app.controller;

     import com.ecommerce.common.test.RuntimeConfigRegistry;
     import com.ecommerce.common.test.SystemClockService;
     import org.slf4j.Logger;
     import org.slf4j.LoggerFactory;
     import org.springframework.http.ResponseEntity;
     import org.springframework.web.bind.annotation.*;

     import java.time.LocalDateTime;
     import java.time.format.DateTimeFormatter;
     import java.time.format.DateTimeParseException;
     import java.util.Map;

     @RestController
     @RequestMapping("/api/v1/admin/system")
     public class SystemAdminController {

         private static final Logger log = LoggerFactory.getLogger(SystemAdminController.class);

         @PutMapping("/configs/{key}")
         public ResponseEntity<Map<String, Object>> putConfig(@PathVariable String key,
                                                               @RequestBody Map<String, Object> body) {
             Object value = body.get("value");
             if (value == null) {
                 return ResponseEntity.badRequest().body(Map.of("error", "value is required"));
             }
             RuntimeConfigRegistry.put(key, value);
             log.info("Config set: {} = {}", key, value);
             return ResponseEntity.ok(Map.of("key", key, "value", value));
         }

         @GetMapping("/configs/{key}")
         public ResponseEntity<Map<String, Object>> getConfig(@PathVariable String key) {
             Object value = RuntimeConfigRegistry.getOrDefault(key);
             if (value == null) {
                 return ResponseEntity.notFound().build();
             }
             return ResponseEntity.ok(Map.of("key", key, "value", value));
         }

         @PutMapping("/clock")
         public ResponseEntity<Map<String, Object>> setClock(@RequestBody Map<String, Object> body) {
             if (body.containsKey("offsetMinutes")) {
                 long offset = ((Number) body.get("offsetMinutes")).longValue();
                 SystemClockService.setOffset(offset);
                 log.info("Clock offset set to {} minutes", offset);
                 return ResponseEntity.ok(Map.of("offsetMinutes", offset));
             } else if (body.containsKey("timestamp")) {
                 String timestamp = (String) body.get("timestamp");
                 try {
                     LocalDateTime fixed = LocalDateTime.parse(timestamp, DateTimeFormatter.ISO_LOCAL_DATE_TIME);
                     SystemClockService.setFixed(fixed);
                     log.info("Clock fixed at {}", fixed);
                     return ResponseEntity.ok(Map.of("timestamp", fixed.toString()));
                 } catch (DateTimeParseException e) {
                     return ResponseEntity.badRequest().body(Map.of("error", "Invalid timestamp format, use ISO_LOCAL_DATE_TIME"));
                 }
             }
             return ResponseEntity.badRequest().body(Map.of("error", "Either offsetMinutes or timestamp is required"));
         }

         @DeleteMapping("/clock")
         public ResponseEntity<Map<String, Object>> resetClock() {
             SystemClockService.reset();
             log.info("Clock reset to system time");
             return ResponseEntity.ok(Map.of("reset", true));
         }
     }
     ```
  3. 在 `SecurityConfig.java` 的 `securityFilterChain()` 里删掉第 63-64 两行 `permitAll()` 规则。其余
     `authorizeHttpRequests` 规则不动（其中 `.requestMatchers("/api/v1/admin/**").hasRole("ADMIN")` 保留——
     `configs`/`clock` 四个端点继续靠这条兜底规则要求 ADMIN 角色）。
- **验收**: `POST /api/v1/admin/system/reset-sandbox` 与 `POST /api/v1/admin/system/bootstrap-admin` 均返回
  **404**（路径不存在，不是 401/403——因为 handler 已被整个删除，不是"改成需要鉴权"）；
  `grep -rn "reset-sandbox\|bootstrap-admin\|resetSandbox\|bootstrapAdmin" code/` 零命中；
  `GET/PUT /api/v1/admin/system/configs/{key}`、`PUT/DELETE /api/v1/admin/system/clock` 四个端点行为完全不变
  （仍需 ADMIN 角色）；`mvn -f code/pom.xml compile` 无未使用 import/参数相关的编译错误。
- **勿犯**: 不要把这两个端点"修"成加个 `.hasRole("ADMIN")` 就收工——`03§5` 的要求是业务代码**完全不得暴露**
  这类接口，不是"要鉴权"；哪怕改成 ADMIN-only，`bootstrap-admin`"免密自签 ADMIN token"这件事本身就是设计
  明禁的后门，必须整个方法删除，而不是加鉴权门槛。同时**不要连坐**删除 `configs`/`clock` 两组端点或它们的
  `RuntimeConfigRegistry`/`SystemClockService` 依赖——这 4 个端点在 README §6.8 冻结列表内，必须原样保留；
  也不要顺手改动 `EventFailureAdminController`/`FaultInjectionAdminController`/`NotificationAdminController`
  等同目录下其它管理支撑控制器，它们不在本卡范围内。

---

### APP-2 | verify-purchase 应允许 USER/ADMIN 双角色访问，实际只放行 USER

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-app/src/main/java/com/ecommerce/app/SecurityConfig.java`
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/controller/OrderController.java`
- **现状**: `GET /api/v1/orders/verify-purchase` 目前没有专属 URL 安全规则，落进
  `SecurityConfig.securityFilterChain()` 第 66 行的通用兜底规则
  `.requestMatchers("/api/v1/**").hasRole("USER")`——只有 USER 角色能访问，ADMIN 角色调用会被拒绝（403）。
  `OrderController` 类级注解 `@PreAuthorize("hasRole('USER')")`（第 36 行）同样只写 USER，其
  `verifyPurchase()` 方法（117-127 行）没有方法级注解覆盖它。**注意**：本仓库当前未启用
  `@EnableMethodSecurity`（详见 APP-3 的"勿犯"），所以无论类级还是方法级 `@PreAuthorize` 目前都是完全不生效
  的死注解，真正决定运行时鉴权行为的只有 `SecurityConfig` 里的 URL 规则。
- **期望**: `verify-purchase` 应同时允许 USER 与 ADMIN 访问。依据: `README.md` §6.5（第 145 行：
  `GET | /api/v1/orders/verify-purchase | USER/ADMIN | 200`）、`design-docs/附录A-API接口参考.md` 第 199
  行（同一端点标注 `USER/ADMIN`）。
- **改法**:
  1. `SecurityConfig.java`：在 `authorizeHttpRequests` 块里 `.requestMatchers("/api/v1/reviews/product/**")
     .permitAll()` 之后、`.requestMatchers("/api/v1/admin/**").hasRole("ADMIN")` **之前**插入一条更具体的
     规则（Spring Security 按声明顺序做首次匹配，具体路径必须排在通用的 `/api/v1/**` 之前才会生效）：
     ```java
     .requestMatchers("/api/v1/orders/verify-purchase").hasAnyRole("USER", "ADMIN")
     ```
     这一行是该路径实际生效的鉴权来源。
  2. `OrderController.java`：给 `verifyPurchase()` 方法补一个方法级注解，紧贴在 `@GetMapping("/verify-purchase")`
     上方：
     ```java
     @PreAuthorize("hasAnyRole('USER', 'ADMIN')")
     ```
     这一步只是让注解与实际契约保持一致（避免日后有人读代码得出"只有 USER"的错误结论），在
     `@EnableMethodSecurity` 未启用的前提下**不产生任何运行时行为变化**——不要误以为加了这个注解就已经解决
     问题，第 1 步的 URL 规则才是让请求真正放行的关键改动。`createOrder`/其余方法上的其它注解
     （如限流、状态码相关，属其它批次）不要动。
- **验收**: 用 ADMIN 角色 JWT 调 `GET /api/v1/orders/verify-purchase?userId=..&productId=..` 返回 200（而非
  403）；USER 角色调用行为不变，仍是 200；`/api/v1/orders/**` 下其余端点（create/detail/list/cancel/batch）
  鉴权行为不变，仍只放行 USER。

---

### APP-3 | 缺失/伪造 JWT 访问受保护接口返回 Spring Security 默认 403 + 非契约错误体，应 401 + {code,message,traceId,details}

- 风险: high · 置信度: definite（已用仓库自带 `SecurityConfigTest` 实测复现）
- **文件**:
  1. `code/ecommerce-app/src/main/java/com/ecommerce/app/security/RestAuthenticationEntryPoint.java`【新增】
  2. `code/ecommerce-app/src/main/java/com/ecommerce/app/security/RestAccessDeniedHandler.java`【新增】
  3. `code/ecommerce-app/src/main/java/com/ecommerce/app/SecurityConfig.java`
  4. `code/ecommerce-app/src/test/java/com/ecommerce/app/config/SecurityConfigTest.java`（既有测试，同步断言）
- **现状**: `JwtAuthFilter`（`ecommerce-user/security/JwtAuthFilter.java`）在 JWT 缺失或校验失败时，只是
  `SecurityContextHolder.clearContext()` 后放行过滤器链（不写响应体），把"未认证"完全交给 Spring Security
  后续环节处理。而 `SecurityConfig.securityFilterChain()`（第 48-73 行）从未调用过 `.exceptionHandling(...)`，
  全仓库也没有任何 `AuthenticationEntryPoint`/`AccessDeniedHandler` 实现——于是 Spring Security 退回内置默认
  行为：`ExceptionTranslationFilter` 用默认的 `Http403ForbiddenEntryPoint`，对**未认证**请求也直接返回
  **403**（而不是 401），响应体是空/非 JSON，且这条路径在 `DispatcherServlet` 派发到 Controller 之前就已经
  被 Security 过滤器链拦下并写了响应，完全绕开 `GlobalExceptionHandler`（后者只覆盖到达 Controller 方法之后
  抛出的异常）。已用仓库自带的（baseline）`SecurityConfigTest` 实测复现：`testUserEndpoints_requireAuth_cart_
  unauthenticated`、`testUserEndpoints_requireAuth_orders_unauthenticated`、`testAdminEndpoints_
  requireAdminRole_unauthenticated`、`testAdminEndpoints_requireAdminRole_post_unauthenticated` 四个"未认证"
  用例断言的都是 `status().isForbidden()`（403），而非契约要求的 401。
- **期望**:
  - 未认证（无 token / token 无效或过期）访问受保护接口 → **401** + 错误体
    `{code:"UNAUTHORIZED", message, traceId, details}`。
  - 已认证但角色不符（如 USER 访问 ADMIN-only 接口）→ **403** + 错误体
    `{code:"FORBIDDEN", message, traceId, details}`。
  依据: `README.md` §7.1（`UNAUTHORIZED | 401` 与 `FORBIDDEN | 403` 是两个不同错误码/状态码）、
  `design-docs/附录A-API接口参考.md` §1（统一错误响应体固定为 `{code, message, traceId, details}` 四字段）。
- **改法**:
  1. 新增包 `com.ecommerce.app.security`，新增两个类，均须标 `@Component`（否则 `SecurityConfig` 构造函数
     无法注入到它们）。两者内部结构几乎对称，`traceId` 生成方式照抄
     `com.ecommerce.common.exception.GlobalExceptionHandler#generateTraceId()` 的既有写法
     （`UUID.randomUUID().toString().substring(0, 8) + "-" + System.currentTimeMillis()`），保持全仓一致；
     `ApiError`（4 参数构造：`code,message,traceId,details`，`details` 传 `null` 时构造函数内部会 fallback
     成空 `HashMap`）与 `AuthorizationException.CODE_UNAUTHORIZED`/`CODE_FORBIDDEN` 常量都是
     `ecommerce-common` 里已存在的类/字段，**不需要新增或修改 common 模块**。

     `RestAuthenticationEntryPoint.java`（实现 `AuthenticationEntryPoint`，处理"未认证"场景，完整目标内容）：
     ```java
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
     ```

     `RestAccessDeniedHandler.java`（实现 `AccessDeniedHandler`，处理"已认证但角色不符"场景，完整目标内容）：
     ```java
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
     ```
  2. `SecurityConfig.java`：注入这两个新 bean，并把它们挂到 app 模块**唯一**这一条 `SecurityFilterChain`
     的 `exceptionHandling(...)` 上：
     - 类顶部加两个 import：`com.ecommerce.app.security.RestAccessDeniedHandler`、
       `com.ecommerce.app.security.RestAuthenticationEntryPoint`；
     - 追加两个 `final` 字段 `restAuthenticationEntryPoint`/`restAccessDeniedHandler`，构造函数追加对应两个
       参数并赋值；
     - 在 `.sessionManagement(...)` 之后、`.authorizeHttpRequests(...)` 之前插入：
       ```java
       .exceptionHandling(handling -> handling
               .authenticationEntryPoint(restAuthenticationEntryPoint)
               .accessDeniedHandler(restAccessDeniedHandler))
       ```
     - `authorizeHttpRequests(...)` 块本身的规则内容不受本卡影响（不管 APP-1/APP-2 两张卡是否已经应用，本卡
       都只加 `exceptionHandling`，不改任何 `requestMatchers` 规则）。
  3. `SecurityConfigTest.java`（既有测试类，`code/` 下允许修改、不计分，但必须同步，否则会把当年复现本 bug
     的测试变成新的红灯）：
     - 内部 `TestConfig` 的 `@Import({...})` 追加 `RestAuthenticationEntryPoint.class,
       RestAccessDeniedHandler.class`；
     - 4 个"未认证"用例断言从 `status().isForbidden()` 改为 `status().isUnauthorized()`：
       `testUserEndpoints_requireAuth_cart_unauthenticated`、
       `testUserEndpoints_requireAuth_orders_unauthenticated`、
       `testAdminEndpoints_requireAdminRole_unauthenticated`、
       `testAdminEndpoints_requireAdminRole_post_unauthenticated`；
     - 2 个"已认证但角色不符"用例**不改**：`testAdminEndpoints_requireAdminRole_withUserRole`、
       `testAdminEndpoints_requireAdminRole_post_withUserRole` 两者都是携带 USER token 访问 ADMIN 接口，
       应继续断言 `isForbidden()`（403）。
- **验收**:
  - 不带 `Authorization` 头（或带一个非法/过期 JWT）调用任意受保护端点（如 `GET /api/v1/orders`、
    `GET /api/v1/admin/system/configs/x`）→ HTTP **401**，响应体可解析为 JSON，含 `code="UNAUTHORIZED"`、
    `message`（非空字符串）、`traceId`（非空字符串）、`details`（存在，等于空对象 `{}`——`ApiError` 构造函数
    对 null details 会 fallback 成空 `HashMap`，不是字段缺失）四个字段。
  - 带合法 USER token 调用 ADMIN-only 端点 → HTTP **403**，响应体同样含 `code="FORBIDDEN"`、`message`、
    `traceId`、`details` 四个字段。
  - `mvn -s maven-settings.xml -f code/pom.xml test -Dtest=SecurityConfigTest` 全绿。
  - 24 例黑盒不回归（本卡只新增"未认证/角色不符"两条异常处理路径，不改变任何已认证且角色正确请求的行为）。
- **勿犯**:
  - 只在 **app 模块** `SecurityConfig` 这**唯一一条** `securityFilterChain()` 的 `exceptionHandling(...)`
    上挂这两个 handler；**绝不新增第二条 `SecurityFilterChain`**（哪怕看起来"更干净更独立"）——两份并存、
    都无 `@Order`/`securityMatcher` 的 filter chain 曾是本仓库真实出现过的 bug（谁生效取决于 Spring bean
    注册顺序，参见第二轮深审 §7 #1，那是 user 批的范围，与本卡无关，但教训通用：本卡只改 app 现有这一条
    chain，不要另起一条）。
  - **绝不加 `@EnableMethodSecurity`**。本卡与 APP-2 都会摸到 `@PreAuthorize`，容易让人觉得"干脆把方法级
    安全启用了更省事、更彻底"——尽调结论是 README §6 全部 61 个端点已被 URL 级 `SecurityConfig` 规则 100%
    覆盖，启用方法级安全**不会修复任何当前可观察行为**，只会让全仓库此前从未被执行过、从未被验证过的
    `@PreAuthorize` 注解突然生效，其中任何一处角色写错就是静默的鉴权行为回归。这与本卡改动目标无关，纯属
    "顺手启用"的陷阱，坚决不碰。
  - 两个新类必须标 `@Component`（不是只在 `SecurityConfig` 里手工 `new`）——`SecurityConfig` 走构造函数注入，
    漏标 `@Component` 会导致 Spring 启动期 `NoSuchBeanDefinitionException`，24 例黑盒直接全灭（上下文起不
    来）。
  - 不要忘记同步 `SecurityConfigTest.java` 的 4 处断言；忘记同步会让这个当年用来复现本 bug 的测试类反过来
    变红，掩盖了修复本身其实是对的。

---

## 跳过条目说明

- **§6.12 #3**（支付回调 `X-Payment-Signature` 头未被读取/校验，位置 `ecommerce-payment/PaymentController.java:52-58`、
  `PaymentCallbackService.java:40-65`）：findings.md 原文已明确注明"根因在 payment 模块，已并入本模块回调
  修复"（findings.md 第 139 行），即已归入 `payment.md`（B06 批）范围，不在本文件重复。
- **§6.12 #4**（事件失败无重放端点，`FailedEventRecord.retried`/`retryCount` 存在却从未被更新，位置
  `EventFailureAdminController.java`，findings.md 标 `suspicious`）：属"事件(S2)"主题（`FailedEventRecord`
  基础设施），且经参考实现核实 `EventFailureAdminController.java` 全程未被改动——不是遗漏，是确认
  过的不做项：README §6.8 冻结的 9 个黑盒管理支撑端点里没有重放端点，findings.md 原文结论也是"属可选增强，
  附加实现不影响契约"。故不成卡。

---

## 附：APP-1+APP-2+APP-3 合并后 `SecurityConfig.java` 完整目标内容（供自查，不是逐条改法）

三张卡都改了这个文件，为避免合并歧义，下面是三卡全部应用之后该文件应有的最终样子（即已通过
全部 24 例公开黑盒验证的参考实现内容，可直接作为整文件替换的目标）：

```java
package com.ecommerce.app;

import com.ecommerce.app.security.RestAccessDeniedHandler;
import com.ecommerce.app.security.RestAuthenticationEntryPoint;
import com.ecommerce.user.security.JwtAuthFilter;
import com.ecommerce.user.service.JwtTokenProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration("appSecurityConfig")
@EnableWebSecurity
public class SecurityConfig {

    private final JwtTokenProvider jwtTokenProvider;
    private final RestAuthenticationEntryPoint restAuthenticationEntryPoint;
    private final RestAccessDeniedHandler restAccessDeniedHandler;

    public SecurityConfig(JwtTokenProvider jwtTokenProvider,
                           RestAuthenticationEntryPoint restAuthenticationEntryPoint,
                           RestAccessDeniedHandler restAccessDeniedHandler) {
        this.jwtTokenProvider = jwtTokenProvider;
        this.restAuthenticationEntryPoint = restAuthenticationEntryPoint;
        this.restAccessDeniedHandler = restAccessDeniedHandler;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean("appSecurityFilterChain")
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session ->
                        session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(handling -> handling
                        .authenticationEntryPoint(restAuthenticationEntryPoint)
                        .accessDeniedHandler(restAccessDeniedHandler))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/v1/users/register").permitAll()
                        .requestMatchers("/api/v1/users/activate").permitAll()
                        .requestMatchers("/api/v1/users/login").permitAll()
                        .requestMatchers("/api/v1/products/**").permitAll()
                        .requestMatchers("/api/v1/inventory/**").permitAll()
                        .requestMatchers("/api/v1/categories/**").permitAll()
                        .requestMatchers("/api/v1/payment/callback").permitAll()
                        .requestMatchers("/api/v1/logistics/callback").permitAll()
                        .requestMatchers("/api/v1/reviews/product/**").permitAll()
                        .requestMatchers("/api/v1/orders/verify-purchase").hasAnyRole("USER", "ADMIN")
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                        .requestMatchers("/api/v1/**").hasRole("USER")
                        .anyRequest().permitAll()
                )
                .addFilterBefore(new JwtAuthFilter(jwtTokenProvider),
                        UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
```

注意：baseline 里第 63-64 行的两条 `reset-sandbox`/`bootstrap-admin` `permitAll()` 规则在这份目标内容里已
不存在（APP-1 删除），`verify-purchase` 那条规则排在 `/api/v1/admin/**` 之前（APP-2 新增），
`exceptionHandling(...)` 整块是新增（APP-3）。三者互不重叠，可任意顺序应用，最终都应收敛到上面这份内容。
