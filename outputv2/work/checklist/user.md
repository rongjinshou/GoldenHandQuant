# checklist: ecommerce-user

依据：`design-docs/04-用户服务设计.md`、附录 A/C/D。相关黑盒：PUB-001、PUB-105。

## 注册 / 激活 / 登录

- [ ] 注册后用户状态是 `PENDING_ACTIVATION`（**不是** `ACTIVE`）；生成并持久化激活令牌（注入 `EmailActivationTokenRepository`）；通知发的是**激活邮件**。（PUB-001/PUB-105 根因）
- [ ] `login()` 对 `USER_NOT_ACTIVE` / `USER_FROZEN` 抛 `AuthorizationException` → **403**（**不是** `BusinessException` → 400）。（PUB-105 第二根因）
- [ ] `activate()` 对已使用/已过期令牌抛 `ConflictException` → **409**（**不是** `BusinessException("CONFLICT")` → 400）。

## 地址

- [ ] `AddressFormatter.format()` 参数顺序为 `(province, city, district, detail)`——设计文档明确「参数顺序不得调整」。
- [ ] 地址 `isDefault` 字段序列化/反序列化的 JSON key 就是 `"isDefault"`（加 `@JsonProperty("isDefault")` 或统一 `getIsDefault/setIsDefault`）；客户端传 `isDefault:true` 不被静默忽略。

## 非功能（见 common）

- [ ] 登录接口有 `@RateLimit`：同用户名 5 次/分钟。
- [ ] 冻结/解冻写审计日志，且能拿到操作者身份（Controller 接收 `Authentication`）。
