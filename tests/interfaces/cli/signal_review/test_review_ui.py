from unittest.mock import MagicMock

from src.application.live_signal_service import SignalDisplay
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.interfaces.cli.signal_review.review_ui import SignalReviewUI, _parse_indices


class TestParseCommand:
    def test_quit(self):
        action, indices = SignalReviewUI._parse_command("q", 5)
        assert action == "quit"
        assert indices == []

    def test_approve_all(self):
        action, indices = SignalReviewUI._parse_command("a", 5)
        assert action == "approve_all"

    def test_reject_all(self):
        action, indices = SignalReviewUI._parse_command("r", 5)
        assert action == "reject_all"

    def test_approve_specific(self):
        action, indices = SignalReviewUI._parse_command("1,3,5", 5)
        assert action == "approve"
        assert indices == [0, 2, 4]

    def test_reject_specific(self):
        action, indices = SignalReviewUI._parse_command("r 2,4", 5)
        assert action == "reject"
        assert indices == [1, 3]

    def test_detail(self):
        action, indices = SignalReviewUI._parse_command("d 3", 5)
        assert action == "detail"
        assert indices == [2]

    def test_note(self):
        action, indices = SignalReviewUI._parse_command("n 1 some note", 5)
        assert action == "note"
        assert indices == [0]

    def test_bare_n_is_next_page(self):
        action, _ = SignalReviewUI._parse_command("n", 5)
        assert action == "next_page"

    def test_next_page_alias(self):
        action, _ = SignalReviewUI._parse_command("next", 5)
        assert action == "next_page"

    def test_prev_page(self):
        action, _ = SignalReviewUI._parse_command("p", 5)
        assert action == "prev_page"

    def test_empty_input(self):
        action, _ = SignalReviewUI._parse_command("", 5)
        assert action == "confirm"

    def test_out_of_range_index_falls_to_confirm(self):
        # "10" is valid numeric but out of range -> indices empty -> falls to confirm
        action, indices = SignalReviewUI._parse_command("10", 5)
        assert action == "confirm"
        assert indices == []


class TestParseIndices:
    def test_single(self):
        assert _parse_indices("3", 5) == [2]

    def test_multiple(self):
        assert _parse_indices("1,3,5", 5) == [0, 2, 4]

    def test_out_of_range(self):
        assert _parse_indices("1,10", 5) == [0]

    def test_non_numeric(self):
        assert _parse_indices("abc", 5) == []

    def test_empty(self):
        assert _parse_indices("", 5) == []


class TestSignalReviewUI:
    def _make_service(self) -> MagicMock:
        service = MagicMock()
        service.account_gateway.get_asset.return_value = MagicMock(
            available_cash=500_000, total_asset=1_000_000,
        )
        service.account_gateway.get_positions.return_value = []
        return service

    def test_init(self):
        service = self._make_service()
        ui = SignalReviewUI(service=service)
        assert ui.service is service
        assert ui.store is not None
