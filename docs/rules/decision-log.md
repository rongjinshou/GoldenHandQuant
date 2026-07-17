# 决策日志 (Decision Log)

> 全自主推进模式下的决策留痕（用户 2026-07-12："干就完事了，做好决策记录"）。
> 每条：日期 | 决策 | 理由 | 证据/详情位置。重大设计决策正文在 docs/feat/ 各设计文档，此处为索引级对账表。

| 日期 | 决策 | 理由（一句话） | 详情 |
|---|---|---|---|
| 2026-07-11 | 影子盘受控化选方案甲（半自动看护），否决全自动 QMT 登录与纯手动 | QMT 人工拉起是硬约束；纯手动实测脱靶率 1/1 | `docs/feat/0711-shadow-control/` |
| 2026-07-11 | 退役 cli/main.py 试单入口 + 两个死模块 | 真网关硬编码下单、无任何闸——"意外下错单"最短路径 | REVIVAL §七 |
| 2026-07-11 | ST 数据源：深市用官方简称变更流；沪市公告标题法经交叉验证 FAIL 不准入 | 准入门 ≥90%≤2td，实测 43%——宁可承认盲区不喂近似数据 | `docs/feat/0711-st-honesty/` |
| 2026-07-11 | 接受临时 tushare 账号（第三方代理），铁律=独立库隔离+运行时零依赖+先验货后信任 | 账号可能失效、代理 HTTP 明文——价值须当晚沉淀为本地资产 | `docs/feat/0711-tushare-asset/` |
| 2026-07-12 | namechange 接口弃用，改 bak_basic 逐日名称推导 ST | 代理上 namechange 反复超时；bak 精度到天且跨沪深 | 同上 §二 |
| 2026-07-12 | 验证器改一对一时序配对 + 停牌窗可观测豁免 | 修复多段 ST 跨段幻影偏差（实测 -722td 假象）；豁免有据（该期无 bars 不可成交） | st_status_source.py + 用例 |
| 2026-07-12 | 停牌诚实债核销为"实测非债"，不接线 | 30,967 全天停牌日中 QMT bars 有行仅 1（量=0）——已被 bars 缺席天然覆盖 | tushare-asset §四 |
| 2026-07-12 | MC-1 市值口径失真立为 P0（QMT 股本字段语义不一致+回填历史） | top20 两口径重叠仅 3/20——策略定义级失真；QMT 字段漂移是持续经营风险 | debt-ledger MC-1 |
| 2026-07-12 | MC-1 处置走 C→A：先离线重验总市值版 gate（PASS），批准后切换总市值口径 | 两口径均 PASS→切换不失过闸资格；定义可解释+免疫 QMT 漂移；周二首采前切换=日历零成本 | `docs/feat/0712-mc1-cap-regime/` |
| 2026-07-12 | v4 补漏收割立即启动（fina_indicator/dividend/top_list/stock_basic/index_weight） | 探针验证可调但 v2/v3 漏收；账号寿命不确定，先抢救数据 | harvest_v4 日志 |
| 2026-07-12 | 迁移计数器以浮点相等判"未迁移", 存在重叠计数——以审计中位比值(三日全 1.000000, >1%差 0)为权威验收 | 计数器语义近似可接受, 审计才是 CTQ | mc1_migration_report.json |
| 2026-07-12 | 发现 instruments.name 5203/5211 只存的是代码本身(从未灌真名), 用 ts_stock_basic 全量修复 | 名称过滤/展示的隐性地基缺陷, 顺手根治 | refresh_instrument_names 输出 |
| 2026-07-12 | pe/pb 同族失真挂 MC-2 观察不扩本轮 scope | F01 不消费 pe/pb; YAGNI, 研究线重启前再审 | debt-ledger MC-2 |
| 2026-07-12 | 日增量市值同步接进影子盘上午段(refresh 后/决策前), 收盘链不加 | 决策吃的是 as-of T-1 行, 上午同步即覆盖; 比对用已落快照无需二次同步 | shadow_ops sync-market-cap 步 |
| 2026-07-12 | gate 等价性验收从"±2pp 数字容差"改为"判据结论一致(双 PASS)+方向一致" | 迁移版含 as-of 回填+2020 预热期覆写, overlay 版不含——数字必然有差(IS ON −13pp), 判据才是 gate 本意; 以迁移版为正式口径 | 0712-mc1 report §等价性 |
| 2026-07-12 | 修 upsert_instruments 防降级覆写(占位名=代码不得冲真名)+_data_wiring 加 DuckDB 分支 | 宇宙解析路径是 5203 只退化名的元凶且会再污染; factor-test 离线路径 WSL 必炸(历史全靠 Windows 掩盖) | market_data_store/upsert + 2 用例 |
| 2026-07-12 | F01 verdict 重跑止损: 挂 Windows 侧执行(interop 恢复后), 不再深修 WSL 离线 ensure | gate 双口径 PASS 已是上钱决策依据; verdict 行属漏斗记账不阻塞周二; WSL 路径已修到 import 安全+缺口诚实报错 | ft_f01.log |
| 2026-07-12 | 研究层全量换代: P0 五因子+价值系六因子 verdict 重跑(离线路径)、纸面净值重跑、0626 阶段0报告标"旧口径勘误" | 口径换代后旧判决/基线=废纸; 单因子全 FAIL 与"挖尽"叙事一致, 上钱依据始终是 gate(双验 PASS) | factor_verdicts run 20260712-*, SHADOW-PAPER-20260712 |
| 2026-07-12 | MC-2 当日顺势核销: pe_ratio←pe_ttm/pb_ratio←pb 全库迁移(审计中位 1.000000); 亏损股 pe 在 ts 侧为空属正确语义, QMT 侧曾有值反而可疑(kept 1.52M 主因) | 泛化迁移机制现成, 研究线地基一次修平 | cap_regime.migrate_fundamental_field |
| 2026-07-12 | E9 首铲: 6 假设双窗 12 判决入库, 晋升 0; R04(低自由流通换手)一窗过一窗 IR 不足→按预声明"双窗皆过"规则列观察名单不晋升, R04b/c 细化假设预注册留待下一轮 | 多重检验纪律高于单窗好看数字; 方向四段全正+中性化双过是保留观察的依据 | docs/feat/0712-ts-factor-mining/ 报告 |
| 2026-07-12 | 资金流因子(R01/R02)判"regime 依赖不可用": 两个十年窗口方向互翻 | 符号不稳的信号比没有信号更危险 | 同上 §一 |
| 2026-07-13 | interop 断路的免重启绕道: 直接调用 /init 作为 interop 代理执行 Windows exe(binfmt 注册丢失但 /init 本体可用) | 无需 root/无需 wsl --shutdown/无需用户动手, 彩排当场自动化 | 本行下方各步实录 |
| 2026-07-13 | 彩排一发被 sync-market-cap 停链(防线正确工作)→修盘中语义: tushare 当日盘后才发布, 改为向前回退≤4 交易日找最近可得日(决策消费本就是 as-of T-1) | "今天没数据"是常态不是漂移; 当日行留给盘后/次晨链自然覆盖 | cap_regime + 新用例; rehearsal.log 实证 |
| 2026-07-13 | 彩排发现挂账: 旧持仓(dual_ma 遗留 5 只)清仓单被盘前闸拦(2 笔金额超 cap、3 笔 002 板白名单外)——SELL 是否应受单笔金额闸约束(退出通道被钱数卡死)+旧持仓过渡, 均归真单 Spec 议题, 不擅改闸门语义 | 影子盘阶段属预期内噪声(执行流水不作一致性口径); 放松实盘闸是业务决策 | 今日 execution_records 5 笔留痕 |
| 2026-07-13 | 盘前闸改"买严卖畅": 主板白名单与单笔金额闸(cap/ceiling)只约束 BUY; SELL 保留时段/新鲜度/价格带/T+1可用量/当日一次/日总额度 | 彩排+今日真实回撤实证: 趋势闸防御性清仓被自家闸拦死(2 笔金额 3 笔白名单), 若真盘=退出失效; 先例=ST 闸 buy-only | pre_trade_checks + 3 用例; 今日 -¥8.2k 持仓浮亏为代价样本 |
| 2026-07-13 | sync_live_account session 动态派生(base+500k+time%100k) | 固定 session 与 auto-trade/任务计划撞车(彩排后 connect!=0 实证), watch 长驻进程必须隔离 | 脚本 + 13:44 快照成功实证 |
| 2026-07-13 | 盘中权益 watch 早夭尸检: /init 派生的 Windows 长驻进程随父 shell 会话退出被带走(13:54 断流) → 裁定: 长驻 Windows 进程一律由任务计划托管, /init 只跑有界命令; 今日 watch 属一次性需求不建常驻 | 真实环境课: 进程生命周期锚点要明确 | equity_watch.log + 快照断点 |
| 2026-07-14 | 补注册每日 15:05 真实账户收盘快照任务(GHQ-Account-EOD, 工作日; QMT 未开则该日自然失败跳过, 无害) | 决策采样按调仓周二(策略语义), 但"你的手"的净值对照曲线值得日频; 影子期两条曲线同粒度才好比 | schtasks 注册记录 |
| 2026-07-14 | 影子盘改日频(用户指令"每天跑半个月"): GHQ-Shadow-Morning/PostClose 改 MON-FRI, 台账双时代(07-14 前周二史料/07-14 起每工作日), G1 重标定"≥10 交易日含 ≥2 调仓周二", G5 容错 MISSED≤2, next_due=下一工作日 | 用户直觉正确: 防御信号(趋势闸/止损)是日频的, 周二采样会漏; 但日频样本相关性高, 独立决策样本仍以周二计数防"样本量幻觉" | shadow_audit.py + 23 用例; 本行上方 EOD 条 |
| 2026-07-14 | 首个全自动日尸检(09:20 链在 sync-market-cap 断, 非 QMT 缺席): (a)计划任务 Windows 进程无 TUSHARE_TOKEN——历次彩排全靠 WSL 会话注入掩盖 → setx 持久化用户环境(仓库外); (b)auto-trade 固定 session 被残留注册顶死(connect!=0 二连) → derive_session_id 下沉 QmtTradeGateway 构造器(+300k 频段与 sync_live_account +500k 错开, 时间×31+pid 同秒不撞), yaml 基值改 123464; (c)观测层双假信号: /init 管道读不到 tasklist 输出(全天误报"QMT 未开", 用户实开着)+WSL 时钟比 Windows 快 1 小时(把提前失败误判成 14:30 超时) → 看护 v3 只盯落库事实+Windows 权威时间 | 环境课三连: 自动化首日必然暴露"人肉在场时不存在"的缺陷; 观测手段本身也要被怀疑(探针一律走 xtquant 权威路径, 时间一律取被观测侧) | 决策快照 20260714-140023 + gateway 4 新用例 + setx 记录 |
| 2026-07-14 | 今日样本盘中抢救成功(真实 14:00 补采, 快照 gate=0 看空/health ok/主板 2238 只): 买严卖畅首次真实环境验证——同样 5 笔防御清仓单昨日 5/5 被拦, 今日 5/5 过闸提交(dry_run 拒绝 0) | 0713 修复的退出通道在真实行情下确证畅通; 系统连续第二日想全清仓 vs 用户持有不动 = 第二个手法分叉样本 | execution_records 20260714 5 笔 + 0713 对照 |
| 2026-07-15 | 全链尸检(用户"看今天战况"触发, 深夜): 三层故障剥洋葱——(a) 07-12 backtest.yaml 切 DuckDB 离线后, 共用该配置的 `quant data refresh` 静默降级为离线空跑(缺口按空返回、退出码 0), 全市场个股 bars/fundamentals 断流 3 交易日(停 07-10)——07-14"VALID"采样实为 5 天陈旧价决策; (b) 07-15 上午链断真凶=sync-market-cap 双源皆败(临时 tushare 账号死亡"无效的token"+akshare 深夜断连; 07-14 靠 akshare 白天兜底幸存)→auto-trade 未跑→07-15 无采样; (c) PostClose/Account-EOD 15:0x 未触发=机器不在线+任务无 StartWhenAvailable 且 DisallowStartIfOnBatteries=true。修复: `resolve_fetcher_type(force_online)` 让 refresh 强制在线(离线桩对"补数"是语义谎言, +3 用例); `ensure_fundamentals` 补 B1 同款履约诚实(空返回不标履约——本次 '*' 水位被离线空跑假标到 07-15 即固化事故); 三 bat 输出落 logs/(无日志无法定位失败步骤是本次尸检最大成本) | 断流三天而无一处告警: 离线降级 print 无人读、exit 0 骗过任务计划、fetch_meta 假履约骗过下轮重试——"诚实失败"必须贯穿每一层 | _data_wiring/data_cmd/market_data_app + tests/interfaces/cli/test_data_wiring.py; 复现实证 scratchpad refresh_full.log |
| 2026-07-15 | 当晚数据抢救(QMT 23 点在线窗口): bars 07-13/14/15 各 5,196-5,199 只 + fundamentals 15,590 行补齐(污染水位回拨 07-10 后重拉), `data status --check` 9 项全 PASS; 07-15 采样如实 MISSED(live 快照不可重建, G5 将至 2/2 零余量, 下一个脱靶日就破闸); 纸面净值 SHADOW-PAPER-20260715 补入无断档(G4); 趋势闸 ON 的纸面策略 07-04 起全程零成交(闸摁在现金)——真实账户同日 -4.87%(-¥8,042, 000021 跌停领跌), 两线分叉本身即影子盘要采的样本 | 抢救窗口是真实约束: 收盘数据当晚可补, 决策快照错过即永失 | backtest_runs SHADOW-PAPER-20260715 + account_snapshots 2026-07-15T23:11 |
| 2026-07-15 | 任务计划设置修正(PostClose/EOD 加 StartWhenAvailable+三任务允许电池启动)被 UAC 二连拒→尊重否决不再弹窗, 正确配置固化进 register_shadow_tasks.ps1(顺带修正: 旧版仍是周频周二+直调 python 的过时语义, 改日频 bat 版并纳入 Account-EOD); Morning 刻意不加补跑——盘后补采样口径漂移, 宁可如实 MISSED | 提权是用户主权; 脚本即可复现文档, 待用户手动管理员执行一次 | scripts/windows/register_shadow_tasks.ps1 |
| 2026-07-15 | 特征断供挂债 FD-1: 5,113 只 stock_features 停 2026-07-03, 未提交 B2 校验的成熟区判定(库内首根 bar+WARMUP)与重算装载窗(warmup_start 起)冲突, 老股窗头 rolling NaN 被误判"成熟区 NULL"→整只拒入不履约且每轮重算重拒; 不夜修 | 交易链不消费 stock_features(07-14 采样在特征停摆下正常运转, 实证), 仅 ML/研究线受影响; B2 校验本意(防 NaN 覆盖好数据)今晚恰好立功——bars 补齐前它正确拦住了残缺特征入库 | debt-ledger FD-1 |
