# B01 · S1-quick-wins — 全局单点速赢

三张卡都是**单点小改、全局生效**的确定性修复，放在第一批：先把最容易的分固化下来。
修完本批立即 `bash work/harness/ratchet.sh verify`。

---

### S1-1 | 金额舍入模式 HALF_DOWN，应为 HALF_UP

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-common/src/main/java/com/ecommerce/common/money/MonetaryUtil.java`
- **现状**: `roundToCent()`（约第 32 行）用 `RoundingMode.HALF_DOWN`（0.005 → 0.00），类 javadoc
  （约第 10 行）与方法注释（约第 25、31 行）也写着 HALF_DOWN。全部金额计算（`add`/`subtract`/
  `multiply` 内部都走 `roundToCent`）经此传播，**全系统金额舍入方向系统性错误**。
- **期望**: 所有金额舍入用 **HALF_UP**（0.005 → 0.01）。依据: `design-docs/03-通用规范与非功能
  设计.md` §1（舍入模式 `RoundingMode.HALF_UP`，入库保留 2 位小数）。
- **改法**: 把 `roundToCent` 的
  `return amount.setScale(SCALE, RoundingMode.HALF_DOWN);`
  改为
  `return amount.setScale(SCALE, RoundingMode.HALF_UP);`
  并把该文件注释里的 `HALF_DOWN` 字样同步改为 `HALF_UP`。**只改这一个文件**——它是全模块金额
  舍入唯一入口，不要去各业务模块重复"修"舍入。
- **验收**: `MonetaryUtil.roundToCent(new BigDecimal("0.005"))` 结果为 `0.01`；
  `grep -rn "HALF_DOWN" code/*/src/main/java` 零命中。

---

### S1-2 | ConflictException 缺 (code, message) 构造函数，带码 409 全部无法抛出

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-common/src/main/java/com/ecommerce/common/exception/ConflictException.java`
- **现状**: 只有 `ConflictException(String message)` 一个构造函数（错误码恒为 `"CONFLICT"`）。
  README §7 里的带码 409（`ORDER_STATUS_CONFLICT`、`REFUND_WAITING_WAREHOUSE_ACCEPT`）因此在
  全仓库**从未被抛出**——业务方想抛也没有入口。后续多张卡片（订单取消/支付冲突/评价重复等）
  都依赖本卡先落地。
- **期望**: 异常体系支持带业务错误码的 409。依据: `design-docs/03` §2（`ConflictException` = 409）、
  `README.md` §7 错误码表。
- **改法**: 在既有构造函数后追加一个重载（其余不动）：

  ```java
  public ConflictException(String code, String message) {
      super(code, message);
  }
  ```

- **验收**: `new ConflictException("ORDER_STATUS_CONFLICT", "...")` 可编译，`getCode()` 返回
  `ORDER_STATUS_CONFLICT`；原单参构造行为不变（code 仍为 `CONFLICT`）。

---

### S1-3 | 错误码 SKU_NOT_AVAILABLE 应为 PRODUCT_NOT_FOR_SALE（两处业务代码 + 同步测试断言）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductQueryServiceImpl.java`
  2. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartValidationService.java`
  3. （同步断言）`code/ecommerce-cart/src/test/java/com/ecommerce/cart/service/CartValidationServiceTest.java`
- **现状**: 商品非在售时，`ProductQueryServiceImpl.getSkuForSale`（约第 60-63 行）与
  `CartValidationService`（约第 46-49 行）都抛
  `new BusinessException("SKU_NOT_AVAILABLE", ...)`——该码**不在** README §7 冻结错误码表中。
- **期望**: 冻结码为 `PRODUCT_NOT_FOR_SALE`（400）。依据: `README.md` §7 错误码表。
- **改法**: 两处业务代码把异常码字符串 `"SKU_NOT_AVAILABLE"` 改为 `"PRODUCT_NOT_FOR_SALE"`
  （message 保持原样）；`CartValidationServiceTest` 里断言该码的测试期望值同步改（`code/` 下
  单测可改、不计分，但不能留红）。
- **验收**: 对非 ON_SHELF 的 SKU 调 `getSkuForSale` / 购物车校验，错误体 `code` 字段为
  `PRODUCT_NOT_FOR_SALE`；`grep -rn "SKU_NOT_AVAILABLE" code/` 零命中。
