"""ST 状态数据源纯函数: 深市区间推导/沪市公告分类/交叉验证(设计 0711-st-honesty §3.2-3.4)。"""
from datetime import date, timedelta

from src.infrastructure.gateway.st_status_source import (
    StEvent,
    StPeriod,
    classify_sh_notices,
    cross_validate,
    derive_periods_from_sz_feed,
    events_to_periods,
)


def _row(d: str, code: str, before: str, after: str) -> dict:
    return {"变更日期": d, "证券代码": code, "变更前简称": before, "变更后简称": after}


class TestDerivePeriodsFromSzFeed:
    def test_enter_and_exit(self):
        rows = [
            _row("2022-05-06", "000021", "深科技", "ST深科技"),
            _row("2023-06-01", "000021", "ST深科技", "深科技"),
        ]
        periods = derive_periods_from_sz_feed(rows)
        assert periods == [StPeriod(
            symbol="000021.SZ", start=date(2022, 5, 6), end=date(2023, 6, 1),
            label="ST", source="szse_name_change",
            evidence="2022-05-06 深科技→ST深科技 | 2023-06-01 ST深科技→深科技",
        )]

    def test_open_interval_when_still_st(self):
        rows = [_row("2024-05-06", "000595", "宝塔实业", "*ST宝实")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.end is None and p.label == "*ST"

    def test_downgrade_star_to_plain_produces_two_periods(self):
        rows = [
            _row("2022-05-06", "002731", "萃华珠宝", "*ST萃华"),
            _row("2023-05-06", "002731", "*ST萃华", "ST萃华"),
            _row("2024-05-06", "002731", "ST萃华", "萃华珠宝"),
        ]
        p1, p2 = derive_periods_from_sz_feed(rows)
        assert (p1.label, p1.start, p1.end) == ("*ST", date(2022, 5, 6), date(2023, 5, 6))
        assert (p2.label, p2.start, p2.end) == ("ST", date(2023, 5, 6), date(2024, 5, 6))

    def test_initial_listing_name_st_counts_from_first_before_name(self):
        # 首条记录的 变更前简称 是该股已知最早名称: 带 ST 则区间自"已知史前"起,
        # 用 date.min 哨兵表示"窗口起点前已在册", loader 展开时按窗口起点截断
        rows = [_row("2021-03-01", "000004", "ST国华", "国华网安")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.start == date.min and p.end == date(2021, 3, 1) and p.label == "ST"

    def test_name_change_without_st_transition_ignored(self):
        rows = [_row("2022-01-04", "000012", "南玻Ａ", "南玻集团")]
        assert derive_periods_from_sz_feed(rows) == []

    def test_symbol_suffix_by_code(self):
        rows = [_row("2022-05-06", "001202", "炬申股份", "ST炬申"),
                _row("2022-07-06", "001202", "ST炬申", "炬申股份")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.symbol == "001202.SZ"


def _next_td(d):
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


def _notice(code: str, title: str, ts: str) -> dict:
    return {"代码": code, "公告标题": title, "公告时间": ts, "公告链接": "http://x"}


class TestClassifyShNotices:
    def test_four_decisive_titles(self):
        rows = [
            _notice("600186", "关于公司股票实施退市风险警示的公告", "2022-05-05 00:00:00"),
            _notice("600186", "关于撤销公司股票退市风险警示的公告", "2023-06-01 00:00:00"),
            _notice("600696", "关于公司股票实施其他风险警示的公告", "2022-07-01 00:00:00"),
            _notice("600696", "关于撤销其他风险警示的公告", "2023-07-03 00:00:00"),
        ]
        events = classify_sh_notices(rows, _next_td)
        kinds = [(e.symbol, e.kind, e.label) for e in events]
        assert ("600186.SH", "enter", "*ST") in kinds
        assert ("600186.SH", "exit", "*ST") in kinds
        assert ("600696.SH", "enter", "ST") in kinds
        assert ("600696.SH", "exit", "ST") in kinds
        # 生效日 = 公告日次交易日: 2022-05-05(周四) -> 05-06(周五)
        enter = next(e for e in events if e.symbol == "600186.SH" and e.kind == "enter")
        assert enter.effective.isoformat() == "2022-05-06"

    def test_noise_titles_excluded(self):
        rows = [
            _notice("600100", "关于公司股票被实施其他风险警示相关事项的进展公告", "2022-01-04 00:00:00"),
            _notice("600100", "关于公司股票交易可能被实施退市风险警示的提示性公告", "2022-01-05 00:00:00"),
            _notice("600100", "关于公司股票继续实施其他风险警示的公告", "2022-01-06 00:00:00"),
            _notice("600100", "关于实施其他风险警示期间所采取的措施的公告", "2022-01-07 00:00:00"),
        ]
        assert classify_sh_notices(rows, _next_td) == []

    def test_non_sh_mainboard_excluded(self):
        rows = [_notice("300555", "关于公司股票实施其他风险警示的公告", "2022-01-04 00:00:00")]
        assert classify_sh_notices(rows, _next_td) == []

    def test_prefix_and_suffix_configurable_for_sz_validation(self):
        rows = [_notice("000021", "关于公司股票实施其他风险警示的公告", "2022-01-04 00:00:00")]
        events = classify_sh_notices(rows, _next_td,
                                     code_prefixes=("000", "001"), suffix=".SZ")
        assert [e.symbol for e in events] == ["000021.SZ"]

    def test_dedupe_same_kind_within_5_days(self):
        rows = [
            _notice("600200", "关于公司股票实施其他风险警示的公告", "2022-03-01 00:00:00"),
            _notice("600200", "关于公司股票实施其他风险警示的公告", "2022-03-03 00:00:00"),
        ]
        assert len(classify_sh_notices(rows, _next_td)) == 1

    def test_downgrade_double_pattern_title(self):
        rows = [_notice("600300", "关于撤销退市风险警示并实施其他风险警示的公告", "2022-06-01 00:00:00")]
        events = classify_sh_notices(rows, _next_td)
        assert [(e.kind, e.label) for e in events] == [("exit", "*ST"), ("enter", "ST")]

    def test_em_tags_cleaned(self):
        rows = [_notice("600400", "关于公司股票实施其他<em>风险</em><em>警示</em>的公告", "2022-06-01 00:00:00")]
        events = classify_sh_notices(rows, _next_td)
        assert len(events) == 1 and events[0].kind == "enter"


class TestEventsToPeriods:
    def test_pairing_and_open_interval(self):
        events = [
            StEvent(symbol="600186.SH", effective=date(2022, 5, 6), kind="enter", label="*ST", evidence="a"),
            StEvent(symbol="600186.SH", effective=date(2023, 6, 2), kind="exit", label="*ST", evidence="b"),
            StEvent(symbol="600696.SH", effective=date(2024, 1, 4), kind="enter", label="ST", evidence="c"),
        ]
        p1, p2 = events_to_periods(events)
        assert (p1.symbol, p1.start, p1.end) == ("600186.SH", date(2022, 5, 6), date(2023, 6, 2))
        assert p2.end is None

    def test_exit_without_enter_ignored(self):
        events = [StEvent(symbol="600400.SH", effective=date(2022, 1, 4), kind="exit", label="ST", evidence="x")]
        assert events_to_periods(events) == []


class TestCrossValidate:
    def test_pass_within_tolerance(self):
        tds = [date(2022, 5, 4) + timedelta(days=i) for i in range(40)]
        tds = [d for d in tds if d.weekday() < 5]
        official = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2022, 6, 6),
                             label="ST", source="szse_name_change", evidence="")]
        inferred = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 9), end=date(2022, 6, 7),
                             label="ST", source="cninfo_notice", evidence="")]
        report = cross_validate(official, inferred, tds)
        assert report["pass"] is True and report["within_2td"] == report["matched"] == 2

    def test_fail_when_deviation_large(self):
        tds = [date(2022, 5, 2) + timedelta(days=i) for i in range(60)]
        tds = [d for d in tds if d.weekday() < 5]
        official = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=None,
                             label="ST", source="szse_name_change", evidence="")]
        inferred = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 20), end=None,
                             label="ST", source="cninfo_notice", evidence="")]
        assert cross_validate(official, inferred, tds)["pass"] is False

    def test_unmatched_official_event_counts_in_details(self):
        tds = [d for d in (date(2022, 5, 2) + timedelta(days=i) for i in range(30))
               if d.weekday() < 5]
        official = [StPeriod(symbol="000099.SZ", start=date(2022, 5, 6), end=None,
                             label="ST", source="szse_name_change", evidence="")]
        report = cross_validate(official, [], tds)
        assert report["matched"] == 0 and report["pass"] is False
        assert report["details"][0]["inferred"] is None


class TestDeriveFromTushareNamechange:
    def test_st_rows_become_periods_end_inclusive_plus_one(self):
        from datetime import date

        from src.infrastructure.gateway.st_status_source import (
            derive_periods_from_tushare_namechange,
        )
        rows = [
            {"ts_code": "600095.SH", "name": "湘财股份", "start_date": "20200930", "end_date": None},
            {"ts_code": "600095.SH", "name": "ST哈高科", "start_date": "20120501", "end_date": "20130430"},
            {"ts_code": "600095.SH", "name": "哈高科", "start_date": "20061009", "end_date": "20120430"},
        ]
        ps = derive_periods_from_tushare_namechange(rows)
        # 仅 ST 行入选; end 语义转为 exclusive(+1 天)以配 loader 的 start<=d<end
        assert len(ps) == 1
        p = ps[0]
        assert p.symbol == "600095.SH" and p.label == "ST"
        assert p.start == date(2012, 5, 1) and p.end == date(2013, 5, 1)
        assert p.source == "tushare_namechange"

    def test_open_period_when_end_nan(self):
        from src.infrastructure.gateway.st_status_source import (
            derive_periods_from_tushare_namechange,
        )
        rows = [{"ts_code": "002731.SZ", "name": "*ST萃华", "start_date": "20260707", "end_date": None}]
        [p] = derive_periods_from_tushare_namechange(rows)
        assert p.end is None and p.label == "*ST"

    def test_non_st_rows_ignored(self):
        from src.infrastructure.gateway.st_status_source import (
            derive_periods_from_tushare_namechange,
        )
        rows = [{"ts_code": "600000.SH", "name": "浦发银行", "start_date": "19991110", "end_date": None}]
        assert derive_periods_from_tushare_namechange(rows) == []


class TestDeriveFromDailyNames:
    def _rows(self, pairs, code="600000.SH"):
        # pairs: [(trade_date, name), ...]
        return [{"trade_date": d, "ts_code": code, "name": n} for d, n in pairs]

    def test_entry_and_exit_day_precise(self):
        from datetime import date

        from src.infrastructure.gateway.st_status_source import derive_periods_from_daily_names
        rows = self._rows([
            ("20220504", "浦发银行"), ("20220505", "ST浦发"),
            ("20220506", "ST浦发"), ("20220509", "浦发银行"),
        ])
        [p] = derive_periods_from_daily_names(rows)
        assert p.start == date(2022, 5, 5) and p.end == date(2022, 5, 9)
        assert p.label == "ST" and p.source == "tushare_bak_basic"

    def test_still_st_at_last_obs_is_open(self):
        from src.infrastructure.gateway.st_status_source import derive_periods_from_daily_names
        rows = self._rows([("20260706", "华峰"), ("20260707", "*ST华峰")], code="002731.SZ")
        [p] = derive_periods_from_daily_names(rows)
        assert p.end is None and p.label == "*ST"

    def test_label_change_splits_period(self):
        from datetime import date

        from src.infrastructure.gateway.st_status_source import derive_periods_from_daily_names
        rows = self._rows([
            ("20220104", "ST某"), ("20220105", "*ST某"), ("20220106", "某股份"),
        ])
        p1, p2 = derive_periods_from_daily_names(rows)
        assert (p1.label, p1.start, p1.end) == ("ST", date(2022, 1, 4), date(2022, 1, 5))
        assert (p2.label, p2.start, p2.end) == ("*ST", date(2022, 1, 5), date(2022, 1, 6))

    def test_never_st_yields_nothing(self):
        from src.infrastructure.gateway.st_status_source import derive_periods_from_daily_names
        assert derive_periods_from_daily_names(self._rows([("20220104", "浦发银行")])) == []

    def test_multi_symbol_independent(self):
        from src.infrastructure.gateway.st_status_source import derive_periods_from_daily_names
        rows = (self._rows([("20220104", "ST甲"), ("20220105", "甲")], code="600001.SH")
                + self._rows([("20220104", "乙"), ("20220105", "ST乙")], code="600002.SH"))
        ps = derive_periods_from_daily_names(rows)
        assert {p.symbol for p in ps} == {"600001.SH", "600002.SH"}


class TestCrossValidatePairing:
    def test_multi_episode_one_to_one_pairing_no_phantom_error(self):
        """同股多段: 2026 官方 end 不得被硬配到 2023 推导 end(幻影 -722td)。
        一对一配对后: 2023↔2023 (0td), 2026 official end 无候选→unmatched。"""
        tds = sorted({date(2022, 1, 3) + timedelta(days=i) for i in range(1700)}
                     - {d for d in (date(2022, 1, 3) + timedelta(days=i) for i in range(1700))
                        if d.weekday() >= 5})
        official = [
            StPeriod(symbol="000004.SZ", start=date(2022, 5, 6), end=date(2023, 6, 28),
                     label="ST", source="szse_name_change", evidence=""),
            StPeriod(symbol="000004.SZ", start=date(2025, 4, 30), end=date(2026, 6, 23),
                     label="*ST", source="szse_name_change", evidence=""),
        ]
        inferred = [
            StPeriod(symbol="000004.SZ", start=date(2022, 5, 6), end=date(2023, 6, 28),
                     label="ST", source="tushare_bak_basic", evidence=""),
            StPeriod(symbol="000004.SZ", start=date(2025, 4, 30), end=None,
                     label="*ST", source="tushare_bak_basic", evidence=""),
        ]
        rep = cross_validate(official, inferred, tds)
        errs = [d["td_error"] for d in rep["details"] if d["td_error"] is not None]
        assert all(abs(e) <= 2 for e in errs)          # 无幻影大偏
        assert rep["matched"] == 3                      # 两 start + 一 end
        unmatched = [d for d in rep["details"] if d["inferred"] is None]
        assert len(unmatched) == 1                      # 2026 官方 end 如实 unmatched

    def test_unobservable_events_excluded_but_counted(self):
        """observable 钩子: 源观测不到的事件(停牌窗)不进准入分母, 单独计数。"""
        tds = [d for d in (date(2022, 1, 3) + timedelta(days=i) for i in range(300))
               if d.weekday() < 5]
        official = [StPeriod(symbol="000585.SZ", start=date(2022, 4, 28), end=None,
                             label="ST", source="szse_name_change", evidence="")]
        rep = cross_validate(official, [], tds,
                             observable=lambda sym, d: False)
        assert rep["total_official"] == 0 and rep["unobservable"] == 1
