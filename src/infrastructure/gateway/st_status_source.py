"""ST 状态数据源 — 深市官方简称变更流推导 + 沪市巨潮公告分类推断。

设计: docs/feat/0711-st-honesty §3.2/§3.3/§3.4。纯函数可离线测试;
akshare I/O 只在 scripts/backfill_st_status.py 薄壳。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.domain.market.value_objects.st_prefixes import is_st_name

SOURCE_SZSE = "szse_name_change"
SOURCE_CNINFO = "cninfo_notice"

_NOISE = ("进展", "提示", "可能", "继续", "期间")
_DEDUPE_DAYS = 5
_OBJECTS = (("退市风险警示", "*ST"), ("其他风险警示", "ST"))


@dataclass(slots=True, kw_only=True, frozen=True)
class StPeriod:
    symbol: str
    start: date            # date.min = 窗口起点前已在册(史前哨兵)
    end: date | None       # None = 至今仍 ST
    label: str             # 'ST' | '*ST'
    source: str
    evidence: str


@dataclass(slots=True, kw_only=True, frozen=True)
class StEvent:
    symbol: str
    effective: date
    kind: str      # 'enter' | 'exit'
    label: str     # 'ST' | '*ST'
    evidence: str


def _label_of(name: str) -> str:
    upper = name.upper()
    return "*ST" if upper.startswith(("S*ST", "*ST")) else "ST"


def derive_periods_from_sz_feed(rows: list[dict]) -> list[StPeriod]:
    """深市简称变更时间线 → ST 区间。同一 symbol 按日期扫描名称序列。"""
    by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        by_symbol.setdefault(str(r["证券代码"]), []).append(r)

    periods: list[StPeriod] = []
    for code, items in sorted(by_symbol.items()):
        items.sort(key=lambda r: str(r["变更日期"]))
        symbol = f"{code}.SZ"
        open_start: date | None = None
        open_label = ""
        trail: list[str] = []

        first_before = str(items[0]["变更前简称"]).replace(" ", "")
        if is_st_name(first_before):
            open_start = date.min
            open_label = _label_of(first_before)

        for r in items:
            day = datetime.strptime(str(r["变更日期"]), "%Y-%m-%d").date()
            before = str(r["变更前简称"]).replace(" ", "")
            after = str(r["变更后简称"]).replace(" ", "")
            trail.append(f"{r['变更日期']} {before}→{after}")
            now_st = is_st_name(after)
            now_label = _label_of(after) if now_st else ""

            if open_start is not None and (not now_st or now_label != open_label):
                periods.append(StPeriod(
                    symbol=symbol, start=open_start, end=day, label=open_label,
                    source=SOURCE_SZSE, evidence=" | ".join(trail),
                ))
                open_start = None
            if now_st and open_start is None:
                open_start, open_label = day, now_label

        if open_start is not None:
            periods.append(StPeriod(
                symbol=symbol, start=open_start, end=None, label=open_label,
                source=SOURCE_SZSE, evidence=" | ".join(trail),
            ))
    return periods


SOURCE_TUSHARE = "tushare_namechange"
SOURCE_BAK_BASIC = "tushare_bak_basic"


def derive_periods_from_daily_names(rows: list[dict]) -> list[StPeriod]:
    """逐日名称快照(trade_date/ts_code/name, 如 tushare bak_basic) → ST 区间。

    day 级精度、跨所全覆盖: 按 symbol 时间线扫描名称序列, ST 前缀出现即进入、
    消失即退出, label 变化(ST↔*ST)拆段。end = 退出日(exclusive, 配 loader);
    末观测日仍 ST → end=None(开区间)。窗口内已 ST(首观测即 ST)以首观测日为起点
    (bak_basic 起 2020, 回测起 2021, 窗口内判定正确)。"""
    by_symbol: dict[str, list[tuple[date, str]]] = {}
    for r in rows:
        name = str(r.get("name") or "").replace(" ", "")
        day = datetime.strptime(str(r["trade_date"])[:8], "%Y%m%d").date()
        by_symbol.setdefault(str(r["ts_code"]), []).append((day, name))

    periods: list[StPeriod] = []
    for symbol, seq in sorted(by_symbol.items()):
        seq.sort(key=lambda x: x[0])
        open_start: date | None = None
        open_label = ""
        for day, name in seq:
            st = is_st_name(name)
            label = _label_of(name) if st else ""
            if open_start is not None and (not st or label != open_label):
                periods.append(StPeriod(
                    symbol=symbol, start=open_start, end=day, label=open_label,
                    source=SOURCE_BAK_BASIC, evidence=f"{open_start}→{day}",
                ))
                open_start = None
            if st and open_start is None:
                open_start, open_label = day, label
        if open_start is not None:
            periods.append(StPeriod(
                symbol=symbol, start=open_start, end=None, label=open_label,
                source=SOURCE_BAK_BASIC, evidence=f"{open_start}→(至末观测)",
            ))
    return periods


def derive_periods_from_tushare_namechange(rows: list[dict]) -> list[StPeriod]:
    """tushare namechange(ts_code/name/start_date/end_date) → ST 区间。

    tushare 直接给带日期的名称区间(比深市变更流更省事): name 命中 ST 前缀即一段
    ST 区间; end_date=NaN/None 为至今。end_date 是该名"最后活跃日"(inclusive),
    转为 exclusive(+1 天)以配 loader 的 `start <= d < end`。跨所全覆盖(交易所级)。
    """
    periods: list[StPeriod] = []
    for r in rows:
        name = str(r.get("name") or "").replace(" ", "")
        if not is_st_name(name):
            continue
        raw_end = r.get("end_date")
        end = None
        if raw_end is not None and str(raw_end) not in ("", "nan", "NaT", "None"):
            end = datetime.strptime(str(raw_end)[:8], "%Y%m%d").date() + timedelta(days=1)
        periods.append(StPeriod(
            symbol=str(r["ts_code"]),
            start=datetime.strptime(str(r["start_date"])[:8], "%Y%m%d").date(),
            end=end, label=_label_of(name), source=SOURCE_TUSHARE,
            evidence=f"{r['start_date']}→{raw_end} {name} ({r.get('change_reason', '')})",
        ))
    periods.sort(key=lambda p: (p.symbol, p.start))
    return periods


def _clean_title(title: str) -> str:
    return title.replace("<em>", "").replace("</em>", "")


def _extract_actions(title: str) -> list[tuple[str, str]]:
    """标题 → [(kind, label)]。宾语("退市/其他风险警示")定位后取就近前置动词
    ("实施"/"撤销")定性——鲁棒于插入词("撤销公司股票退市风险警示")与
    降档双动作标题("撤销退市风险警示并实施其他风险警示")。"""
    actions: list[tuple[str, str]] = []
    for obj, label in _OBJECTS:
        pos = 0
        while True:
            i = title.find(obj, pos)
            if i == -1:
                break
            head = title[:i]
            v_enter = head.rfind("实施")
            v_exit = head.rfind("撤销")
            if v_enter >= 0 or v_exit >= 0:
                kind = "enter" if v_enter > v_exit else "exit"
                actions.append((kind, label))
            pos = i + len(obj)
    return actions


def classify_sh_notices(
    rows: list[dict],
    next_trading_day: Callable[[date], date],
    *,
    code_prefixes: tuple[str, ...] = ("60",),
    suffix: str = ".SH",
) -> list[StEvent]:
    """巨潮公告标题 → 决定性 ST 事件(默认沪市主板 60 开头)。

    生效日 = 公告日次一交易日(交易所规则: 实施/撤销于公告后首个交易日生效)。
    降档公告("撤销退市风险警示并实施其他风险警示")拆成 exit(*ST)+enter(ST)。
    code_prefixes/suffix 可配置: 交叉验证时以深市代码跑同一管道对照官方流(§3.4)。
    """
    raw: list[StEvent] = []
    for r in rows:
        code = str(r["代码"])
        if not code.startswith(code_prefixes):
            continue
        title = _clean_title(str(r["公告标题"]))
        if any(w in title for w in _NOISE):
            continue
        ann_day = datetime.strptime(str(r["公告时间"])[:10], "%Y-%m-%d").date()
        eff = next_trading_day(ann_day)
        ev = f"{title} @{r['公告时间']} {r.get('公告链接', '')}"
        symbol = f"{code}{suffix}"

        for kind, label in _extract_actions(title):
            raw.append(StEvent(symbol=symbol, effective=eff, kind=kind, label=label, evidence=ev))

    # 同 symbol 同 kind+label 在 _DEDUPE_DAYS 内去重取首条
    raw.sort(key=lambda e: (e.symbol, e.kind, e.label, e.effective))
    deduped: list[StEvent] = []
    for e in raw:
        prev = deduped[-1] if deduped else None
        if (prev is not None and prev.symbol == e.symbol and prev.kind == e.kind
                and prev.label == e.label
                and (e.effective - prev.effective).days <= _DEDUPE_DAYS):
            continue
        deduped.append(e)
    deduped.sort(key=lambda e: (e.symbol, e.effective, 0 if e.kind == "exit" else 1))
    return deduped


def events_to_periods(events: list[StEvent]) -> list[StPeriod]:
    """enter/exit 事件配对成区间; 无 enter 的 exit 丢弃(窗口前已在册的沪市情形
    由回填脚本用终态自洽检查兜底, 见 §3.4)。"""
    periods: list[StPeriod] = []
    open_map: dict[str, StEvent] = {}
    for e in events:
        if e.kind == "enter":
            if e.symbol not in open_map:
                open_map[e.symbol] = e
        else:
            start = open_map.pop(e.symbol, None)
            if start is not None:
                periods.append(StPeriod(
                    symbol=e.symbol, start=start.effective, end=e.effective,
                    label=start.label, source=SOURCE_CNINFO,
                    evidence=f"{start.evidence} || {e.evidence}",
                ))
    for e in open_map.values():
        periods.append(StPeriod(
            symbol=e.symbol, start=e.effective, end=None, label=e.label,
            source=SOURCE_CNINFO, evidence=e.evidence,
        ))
    periods.sort(key=lambda p: (p.symbol, p.start))
    return periods


def cross_validate(official: list[StPeriod], inferred: list[StPeriod],
                   trading_days: list[date], *,
                   observable=None,
                   max_pair_days: int = 45) -> dict:
    """推断源(inferred)对官方(official)的日期误差分布。

    准入: ≥90% 对齐事件 ≤2 交易日且平均带符号误差 |mean| ≤ 1 天; 零对齐 = FAIL。
    start/end 分别作为独立事件, 同 (symbol, kind) 内**按时序一对一贪心配对**
    (候选不复用, 距离 > max_pair_days 不硬配)——修复多段 ST 时跨段幻影大偏。
    observable(symbol, day): 源观测不到的官方事件(如停牌窗内)不进准入分母,
    计入 unobservable 单独报告。"""
    ordered = sorted(trading_days)
    idx = {d: i for i, d in enumerate(ordered)}

    def td_dist(a: date, b: date) -> int | None:
        ka = next((d for d in ordered if d >= a), None)
        kb = next((d for d in ordered if d >= b), None)
        if ka is None or kb is None:
            return None
        return idx[kb] - idx[ka]

    inferred_map: dict[tuple[str, str], list[date]] = {}
    for p in inferred:
        inferred_map.setdefault((p.symbol, "start"), []).append(p.start)
        if p.end is not None:
            inferred_map.setdefault((p.symbol, "end"), []).append(p.end)

    # 官方事件按 (symbol, kind) 分组
    official_events: dict[tuple[str, str], list[date]] = {}
    unobservable = 0
    for p in official:
        for kind, day in (("start", p.start), ("end", p.end)):
            if day is None or day == date.min:
                continue
            if observable is not None and not observable(p.symbol, day):
                unobservable += 1
                continue
            official_events.setdefault((p.symbol, kind), []).append(day)

    details = []
    matched = within = 0
    signed_sum = 0
    total_official = 0
    for key, days in sorted(official_events.items()):
        symbol, kind = key
        cands = sorted(inferred_map.get(key, []))
        used = [False] * len(cands)
        # 全对距离贪心: 最近的先配, 候选不复用, 超 max_pair_days 不配
        pairs = sorted(
            ((abs((c - day).days), oi, ci)
             for oi, day in enumerate(sorted(days))
             for ci, c in enumerate(cands)),
        )
        days_sorted = sorted(days)
        assigned: dict[int, int] = {}
        for dist, oi, ci in pairs:
            if dist > max_pair_days or oi in assigned or used[ci]:
                continue
            assigned[oi] = ci
            used[ci] = True
        for oi, day in enumerate(days_sorted):
            total_official += 1
            ci = assigned.get(oi)
            if ci is None:
                details.append({"symbol": symbol, "kind": kind, "official": day.isoformat(),
                                "inferred": None, "td_error": None})
                continue
            err = td_dist(day, cands[ci])
            if err is None:
                continue
            matched += 1
            signed_sum += err
            if abs(err) <= 2:
                within += 1
            details.append({"symbol": symbol, "kind": kind, "official": day.isoformat(),
                            "inferred": cands[ci].isoformat(), "td_error": err})

    mean_signed = signed_sum / matched if matched else 0.0
    ok = matched > 0 and within / matched >= 0.9 and abs(mean_signed) <= 1.0
    return {"matched": matched, "total_official": total_official, "within_2td": within,
            "mean_signed_td": round(mean_signed, 2), "pass": ok,
            "unobservable": unobservable, "details": details}
