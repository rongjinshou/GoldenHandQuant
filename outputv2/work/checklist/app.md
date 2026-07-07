# checklist: ecommerce-app

依据：`design-docs/02-系统架构.md`、`03` §5、README 第 6 节冻结契约。app 是启动/安全/测试支撑模块。

## 安全（design-docs/03 §5 禁止 reset/bootstrap 接口）

- [ ] `SystemAdminController` 的 `reset-sandbox` / `bootstrap-admin` 两个接口**整个删除**，并删除 `SecurityConfig` 里对应的 `permitAll()` 放行——这是未鉴权即可清库/自签 ADMIN token 的安全漏洞，且属设计禁止暴露的 reset/bootstrap 钩子。（黑盒隔离由 harness 负责，业务代码不得自带 reset）
- [ ] 保留 configs/clock 等测试支撑端点原样（这些是 harness 需要的，非 reset 钩子）。

## 鉴权契约

- [ ] `/api/v1/orders/verify-purchase` 放行 **USER + ADMIN**（附录 A/README 要求两者都可访问，基线只放行 USER）。
- [ ] 注意：全仓**无 `@EnableMethodSecurity`**，Controller 上的类级/方法级 `@PreAuthorize` 实际不生效，真正鉴权在 `SecurityConfig` 的 URL 规则——放开 ADMIN 要改的是 URL 规则（在 `/api/v1/**` 之前显式加 `verify-purchase → hasAnyRole(USER,ADMIN)`）。

## 启动完整性（集成）

- [ ] Spring 上下文能启动：跨模块同简单名的组件（如 logistics/loyalty 的 `OrderPaidEventListener`）已用显式模块限定 bean 名去冲突，无 `ConflictingBeanDefinitionException`。
- [ ] 删除影子类后，`DuplicateClassNameExcludeFilter` 等排除配置无指向已删类的死条目。

## 支付回调签名（根因在 payment，此处仅确认贯通）

- [ ] 支付回调 `X-Payment-Signature` 头被读取并校验（实现在 payment 模块，见 payment 清单）。

## 可选增强（不影响冻结契约）

- [ ] 事件失败重放端点：README 冻结的 9 个 admin 端点不含重放，`FailedEventRecord.retried/retryCount` 可留作附加实现，缺失不算契约违背。`[suspicious]`
