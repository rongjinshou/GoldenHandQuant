# A 股领域规则建模规范 (Domain Rules)

> 设计领域模型与回测/实盘网关时必须内置的 A 股业务规则，保证回测与实盘逻辑一致。

## 1. 结算与资产

1. **T+1**: `Position` 区分 `total_volume`（总持仓）与 `available_volume`（可用持仓）。
   当日买入只增加 `total_volume`（当日不可卖）；日终 `settle_t_plus_1()` 将可用量
   同步为总量。
2. **资金冻结**: `Asset` 包含 `total_asset` / `available_cash` / `frozen_cash`。
   订单提交（SUBMITTED）时立即冻结资金，成交（FILLED）/撤单（CANCELED）时对应
   解冻或扣减。三个独立方法：`freeze_cash()` / `unfreeze_cash()` / `deduct_frozen_cash()`。
3. **订单状态机**（单向流转，禁止逆向，实现用 `match/case`）：
   - `CREATED → SUBMITTED`
   - `SUBMITTED → PARTIAL_FILLED / FILLED / CANCELED / REJECTED`
   - `PARTIAL_FILLED → FILLED / PARTIAL_CANCELED`

## 2. 价格与数量约束

- **买入**申报数量必须为 100 的整数倍（一手）。
- **卖出**允许零股（非 100 整数倍的残股必须可一次清仓，闸函数
  `check_sell_volume` 已按此实现——禁止把买入约束误加在卖出上）。
- 行情特征计算必须使用**前复权**数据（`dividend_type='front'`）。

## 3. 交易成本（严禁无摩擦假设）

费率通过 `CostsSettings` 配置化，回测撮合与实盘资金计算共用：

1. **佣金**: 双向，默认万 2.5（0.00025），**单笔最低 5 元**（滤除实盘无法获利的微利信号）。
2. **印花税**: 仅卖出，默认千 0.5（0.0005）。
3. **过户费**: 双向，默认十万分之一（0.00001）。

## 4. 滑点与流动性（Mock 网关必须实现）

1. **滑点**: 买入成交价 = 参考价 × (1 + slippage)，卖出 = 参考价 × (1 − slippage)，
   默认 0.1%。
2. **成交容量**: 单笔 `volume` 不得超过当日 K 线总量的 10%；超出部分标记
   `PARTIAL_CANCELED`，严禁无流动性假定下的巨额成交。
3. **涨跌停**: 通过 `PriceLimit` 值对象校验，触及涨跌停的订单 `REJECTED`。

## 5. 复权价与真实成交价分离

1. **策略计算用复权价**: `Bar.open/high/low/close` 存前复权价，保证指标连续性。
2. **账户结算用不复权价**: `Bar.unadjusted_close` 存真实成交价，
   `MockTradeGateway._simulate_fill()` 以此计费与更新资产。
3. **收盘强制撤单**: 跨日回测时所有未成交订单（SUBMITTED / PARTIAL_FILLED）日终
   流转为 CANCELED（A 股报单当日有效），由
   `DailySettlementService.process_daily_settlement()` 统一处理
   （`src/domain/account/services/settlement_service.py`）。

## 6. StockSnapshot 数据模型

截面策略与因子体系的核心输入（`src/domain/market/value_objects/stock_snapshot.py`）：

1. 内部拆分为三个 `frozen=True` 子对象：`PriceVolumeData` / `FundamentalData` /
   `TechnicalIndicators`；新增字段必须归入正确子对象，不得在顶层直接加。
2. 通过 `__getattr__` / `__setattr__` 代理保持 flat 访问向后兼容。
3. 构造函数保留 `**_extra: object` 忽略未知字段，提升数据兼容性。

## 7. 通知与状态文件安全

- **通知脱敏**: 交易通知中价格只保留整数、数量用模糊级别（`1K 级`、`>5W`），
  避免泄露精确交易信息。
- **状态文件完整性**: 持久化状态文件（如暂停状态 JSON）附带 HMAC 签名，
  加载时校验防篡改（`AutoPauseManager` 已实现）。
