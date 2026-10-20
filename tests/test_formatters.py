"""네트워크 호출 없이 포맷터만 검증하는 스모크 테스트."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.formatters import bond_message, common, stock_message  # noqa: E402

FIXTURE_SNAPSHOT = {
    "trade_date": "2026-10-16",
    "indices": {
        "S&P500": {"ok": True, "value": 5800.12, "prev_value": 5790.00, "change_pct": 0.175},
        "NASDAQ": {"ok": True, "value": 18200.5, "prev_value": 18100.0, "change_pct": 0.555},
        "DOW": {"ok": True, "value": 41000.0, "prev_value": 41200.0, "change_pct": -0.485},
        "DXY": {"ok": False, "reason": "timeout"},
    },
    "top20_stocks": [
        {"ticker": "AAPL", "name": "Apple", "ok": True, "value": 230.0, "change_pct": 1.2},
        {"ticker": "MSFT", "name": "Microsoft", "ok": False, "reason": "timeout"},
    ],
    "rates": {
        "US10Y": {"ok": True, "value": 5.09, "prev_value": 5.10, "change_bp": -1.0, "trade_date": "2026-10-16"},
    },
    "failures": [{"item": "DXY", "reason": "timeout"}, {"item": "MSFT", "reason": "timeout"}],
    "anomalies": [],
}


def test_trade_date_header():
    assert common.format_trade_date_header("2026-10-16") == "10/16(금) 마감"


def test_bp_formatting():
    assert common.format_bp(-1.0) == "-1bp"
    assert common.format_bp(2.0) == "+2bp"
    assert common.format_bp(0.0) == "0bp"


def test_label_thresholds():
    assert common.label_for_group([{"ok": True, "change_pct": 1.0}]) == "(강세)"
    assert common.label_for_group([{"ok": True, "change_pct": -1.0}]) == "(약세)"
    assert common.label_for_group([{"ok": True, "change_pct": 0.1}]) == "(혼조)"


def test_stock_message_skips_failed_sections():
    text = stock_message.build_stock_message(FIXTURE_SNAPSHOT)
    assert "10/16(금) 마감" in text
    assert "달러인덱스" not in text  # DXY 실패 -> 섹션 생략
    assert "Microsoft" not in text    # 실패 종목 생략
    assert "Apple" in text


def test_bond_message_uses_bp():
    text = bond_message.build_bond_message(FIXTURE_SNAPSHOT)
    assert "-1bp" in text
    assert "5.09%" in text


if __name__ == "__main__":
    test_trade_date_header()
    test_bp_formatting()
    test_label_thresholds()
    test_stock_message_skips_failed_sections()
    test_bond_message_uses_bp()
    print("all tests passed")
