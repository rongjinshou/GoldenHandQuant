# checklist: ecommerce-product

依据：`design-docs/05-商品服务设计.md`、附录 A/C。

## 库存与售卖态

- [ ] 库存摘要走真实 `InventoryQueryService`（**不是**硬编码返回 999/0）。
- [ ] `getSkuForSale` 不可售时抛 `PRODUCT_NOT_FOR_SALE`（**不是** `SKU_NOT_AVAILABLE`；cart 侧同名错误码也要一致）。

## 搜索

- [ ] 默认 `onlyOnShelf=true`，或匿名端点强制只返回 `ON_SHELF`——未上架/草稿商品不得泄漏到公开列表。
- [ ] 类目过滤**含子类目**（解析类目树取后代 ID 集合再过滤）。
- [ ] 标签(tags)过滤字段被真正读取并生效。
- [ ] 分页 `total` 在类目/品牌过滤时正确——过滤下推到 DB 层 Specification，**不是**先 DB 分页再内存过滤。
- [ ] 关键词搜索至少匹配 SPU 名（不只 SKU 名）。`[suspicious]`

## 非功能

- [ ] 商品上下架写审计日志。
- [ ] 商品详情有 10 分钟缓存（仿 Caffeine 配置）。
- [ ] 商品搜索接口有 `@RateLimit`：120 次/分钟/IP。
