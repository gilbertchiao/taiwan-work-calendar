"""單年 JSON 結構組裝。"""

from __future__ import annotations

from .model import build_year_days


def merge_records(tpe_records: dict, nwt_records: dict) -> dict:
    """合併兩來源記錄，臺北優先（含臺北獨有的特定節日等資訊）。

    isWorkday 已於 reconcile 階段確認一致，故合併不影響上班判斷，
    僅讓 name/description 等資訊更完整。
    """
    merged = dict(nwt_records)
    merged.update(tpe_records)
    return merged


def build_year(year: int, records: dict, sources: list[str]) -> dict:
    """組出單年完整結構。"""
    days = build_year_days(year, records)
    workdays = sum(1 for day in days if day["isWorkday"])
    total = len(days)
    return {
        "year": year,
        "sources": sources,
        "summary": {
            "total": total,
            "workdays": workdays,
            "holidays": total - workdays,
        },
        "days": days,
    }
