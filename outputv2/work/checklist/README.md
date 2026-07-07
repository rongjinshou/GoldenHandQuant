# Stage 3 逐模块验证清单（checklist/）

本目录是三段式流水线 **Stage 3（在线复核）** 的核对辅助。每个文件对应 ShopHub 的一个业务模块，把该模块**关键的设计契约点**整理成可扫读的核对项，供 `work/skills/design-consistency-fixer/SKILL.md` 在**出现失败/跳过用例时**按模块加载。

## 怎么用

- 这些清单**不是**默认逐份通读的。正常路径下 Stage 2（`apply.sh`）已把已知不一致确定性修好，Stage 3 先跑验证套件，**全绿就不进这里**（只做轻量抽查）。
- 只有当某个 `pubNNN_*` 黑盒用例失败、或 apply-report 有 skipped/failed 时，才把该失败映射到模块，打开对应清单深核。
- 每条核对项写的是「**看什么 → 期望什么（设计依据）**」，你只需**核对 + 机械修正**，不需要自己从设计文档反推期望值——发现环节已在 Stage 1 离线审查中做掉。
- 修复必须走 SKILL.md §3.2 的护栏：**备份 → 单模块编译门控 → 重跑黑盒 → 通过数下降或编译失败则回滚**。
- **朝设计契约修，绝不针对具体测试用例硬编码。** 期望值一律以 `design-docs/` 与 README 第 6/7 节冻结契约为准。

## 模块 → 清单 → 设计文档

| 清单 | 模块 artifactId | 主设计文档 |
|---|---|---|
| `common.md` | ecommerce-common | `03-通用规范与非功能设计.md`、`15-本地通知组件设计.md`、附录 C/D |
| `user.md` | ecommerce-user | `04-用户服务设计.md` |
| `product.md` | ecommerce-product | `05-商品服务设计.md` |
| `inventory.md` | ecommerce-inventory | `06-库存服务设计.md` |
| `cart.md` | ecommerce-cart | `07-购物车服务设计.md` |
| `order.md` | ecommerce-order | `08-订单服务设计.md` |
| `payment.md` | ecommerce-payment | `09-支付服务设计.md`、`14-发票与结算设计.md` |
| `promotion.md` | ecommerce-promotion | `10-促销服务设计.md` |
| `logistics.md` | ecommerce-logistics | `11-物流服务设计.md` |
| `loyalty.md` | ecommerce-loyalty | `12-积分与会员服务设计.md` |
| `review.md` | ecommerce-review | `13-评价服务设计.md` |
| `app.md` | ecommerce-app | `02-系统架构.md`、`03` §5 |

标注 `[suspicious]` 的条目在设计文档中未写死或改动面较大，深核时需谨慎：优先确认没有黑盒用例断言具体字符串/行为再改，宁可不改也不要「为改而改」引入新的不一致。
