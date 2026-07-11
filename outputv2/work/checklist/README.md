# 逐模块强规则速查（checklist/）

每个文件对应 ShopHub 的一个业务模块，把该模块**关键的设计契约点**整理成可扫读的核对项。
在批次修复流程（`INSTRUCTION.md` → `work/bugs/README.md` 批次表）里有两个用途：

- **修完自查**：subagent 修完一批卡片后（`work/skills/bug-fixer/SKILL.md` 工作流第 4 步），
  扫一遍本模块清单，确认本批卡片的验收点都已满足；
- **失败排查**：某批 `ratchet.sh verify` 被回滚、或个别 `pubNNN_*` 用例始终不绿时，把失败
  映射到模块，打开对应清单核对「**看什么 → 期望什么（设计依据）**」，定位是哪张卡没改对
  或改漏了。

每条核对项只需**核对 + 机械修正**，不需要从设计文档反推期望值——发现环节已在离线审查中
做掉，修复的具体步骤在 `work/bugs/` 对应批次的卡片里。
**朝设计契约修，绝不针对具体测试用例硬编码。** 期望值一律以 `design-docs/` 与 README
第 6/7 节冻结契约为准。

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

标注 `[suspicious]` 的条目在设计文档中未写死或改动面较大，排查时需谨慎：优先确认没有黑盒
用例断言具体字符串/行为再改，宁可不改也不要「为改而改」引入新的不一致。
