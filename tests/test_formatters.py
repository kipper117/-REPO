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
        {"ticker": "AAPL", "name_kr": "애플", "sector": "기술", "ok": True, "value": 230.0, "change_pct": 1.2},
        {"ticker": "MSFT", "name_kr": "마이크로소프트", "sector": "기술", "ok": False, "reason": "timeout"},
        {"ticker": "XOM", "name_kr": "엑슨모빌", "sector": "에너지", "ok": True, "value": 110.0, "change_pct": -0.8},
    ],
    "rates": {
        "US10Y": {"ok": True, "value": 5.09, "prev_value": 5.10, "change_bp": -1.0, "trade_date": "2026-10-16"},
        "US30Y": {"ok": False, "reason": "timeout"},
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


def test_arrows():
    assert common.arrow_for_pct(1.0) == "▲"
    assert common.arrow_for_pct(-1.0) == "▼"
    assert common.arrow_for_pct(0.0) == "➖"
    assert common.arrow_for_bp(-1.0) == "▼"


def test_label_thresholds():
    assert common.label_for_group([{"ok": True, "change_pct": 1.0}]) == "(강세)"
    assert common.label_for_group([{"ok": True, "change_pct": -1.0}]) == "(약세)"
    assert common.label_for_group([{"ok": True, "change_pct": 0.1}]) == "(혼조)"


def test_stock_section_skips_failed_sections_and_groups_by_sector():
    text = stock_message.build_stock_section(FIXTURE_SNAPSHOT)
    assert "10/16(금) 마감" in text
    assert "달러인덱스" not in text          # DXY 실패 -> 섹션 생략
    assert "마이크로소프트" not in text        # 실패 종목 생략
    assert "애플" in text and "AAPL" in text
    assert "기술" in text and "에너지" in text  # 섹터 헤더 존재
    assert "▲" in text and "▼" in text


def test_bond_section_uses_bp_and_skips_failed_rate():
    text = bond_message.build_bond_section(FIXTURE_SNAPSHOT)
    assert "-1bp" in text
    assert "5.09%" in text
    assert "10년물" in text
    assert "30년물" not in text  # US30Y 실패 -> 해당 줄 생략


def test_bond_section_none_when_all_rates_fail():
    snap = dict(FIXTURE_SNAPSHOT, rates={"US10Y": {"ok": False}, "US30Y": {"ok": False}})
    assert bond_message.build_bond_section(snap) is None


if __name__ == "__main__":
    test_trade_date_header()
    test_bp_formatting()
    test_arrows()
    test_label_thresholds()
    test_stock_section_skips_failed_sections_and_groups_by_sector()
    test_bond_section_uses_bp_and_skips_failed_rate()
    test_bond_section_none_when_all_rates_fail()
    print("all tests passed")
