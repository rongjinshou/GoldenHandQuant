"""order_poller 测试（2026-07-10 六西格玛体检 D5 — 补零覆盖实盘模块）。

该 helper 是 auto-trade 与 ticket 手动下单共用的轮询核心(债 D1 收敛产物),
超时撤单分支直接决定「收盘前意外敞口」是否被回收, 此前 0 覆盖。
时钟/休眠全部注入 Fake, 不真实等待。
"""

from src.domain.trade.services.order_poller import (
    TERMINAL_STATES,
    poll_order_until_terminal,
)


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _poll(statuses, *, cancel_results=None, cancel_on_timeout=False, timeout=30.0):
    """驱动一次轮询: statuses 依次弹出, 耗尽后返回 'ALIVE'。"""
    clock = FakeClock()
    seq = list(statuses)
    canceled: list[str] = []
    cancel_seq = list(cancel_results or [True])

    def query(order_id):
        return seq.pop(0) if seq else "ALIVE"

    def cancel(order_id):
        canceled.append(order_id)
        return cancel_seq.pop(0) if cancel_seq else True

    result = poll_order_until_terminal(
        "o-1", query_status=query, cancel_order=cancel,
        timeout_seconds=timeout, poll_interval=2.0,
        clock=clock, sleep=lambda s: clock.advance(s),
        cancel_on_timeout=cancel_on_timeout,
    )
    return result, canceled


class TestTerminalStates:
    def test_reaches_filled_and_records_trail(self):
        result, canceled = _poll(["ALIVE", "PARTIAL", "FILLED"])

        assert result.final_status == "FILLED"
        assert result.canceled is False
        assert [t["status"] for t in result.trail] == ["ALIVE", "PARTIAL", "FILLED"]
        assert canceled == []

    def test_each_terminal_state_stops_polling(self):
        for terminal in TERMINAL_STATES:
            result, _ = _poll([terminal])
            assert result.final_status == terminal

    def test_trail_dedupes_consecutive_same_state(self):
        result, _ = _poll(["ALIVE", "ALIVE", "ALIVE", "FILLED"])

        assert [t["status"] for t in result.trail] == ["ALIVE", "FILLED"]


class TestTimeoutBranches:
    def test_timeout_without_cancel_keeps_last_state(self):
        """ticket 手动路径(cancel_on_timeout=False): 超时不撤, 报最后所见状态。"""
        result, canceled = _poll(["ALIVE"], cancel_on_timeout=False, timeout=6.0)

        assert result.final_status == "ALIVE"
        assert result.canceled is False
        assert canceled == []

    def test_timeout_with_no_state_seen_reports_timeout(self):
        # timeout=4s/间隔2s 恰好查询两次, 两次都给 None(网关始终无应答)
        result, _ = _poll([None, None], cancel_on_timeout=False, timeout=4.0)

        assert result.final_status == "TIMEOUT"

    def test_timeout_cancel_success(self):
        """auto-trade 路径: 超时撤单成功 → TIMEOUT_CANCELED, 敞口已回收。"""
        result, canceled = _poll(
            ["ALIVE"], cancel_on_timeout=True, cancel_results=[True], timeout=6.0)

        assert result.final_status == "TIMEOUT_CANCELED"
        assert result.canceled is True
        assert canceled == ["o-1"]

    def test_timeout_cancel_rejected_flags_manual_followup(self):
        """撤单未受理 → TIMEOUT_UNCANCELED(需人工), 绝不能伪装成已撤。"""
        result, canceled = _poll(
            ["ALIVE"], cancel_on_timeout=True, cancel_results=[False], timeout=6.0)

        assert result.final_status == "TIMEOUT_UNCANCELED"
        assert result.canceled is False
        assert canceled == ["o-1"]
