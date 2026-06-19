"""兩來源逐日比對推導後的 isWorkday。"""

from __future__ import annotations

from .errors import SourceMismatchError
from .model import build_year_days


def reconcile_year(year: int, tpe_records: dict, nwt_records: dict) -> None:
    """比對兩來源該年每日 isWorkday，不一致則拋 SourceMismatchError。"""
    tpe_days = {d["date"]: d for d in build_year_days(year, tpe_records)}
    nwt_days = {d["date"]: d for d in build_year_days(year, nwt_records)}

    diffs: list[dict] = []
    for date_str in sorted(tpe_days):
        tpe_day = tpe_days[date_str]
        nwt_day = nwt_days[date_str]
        if tpe_day["isWorkday"] != nwt_day["isWorkday"]:
            diffs.append(
                {
                    "date": date_str,
                    "tpe": tpe_day["isWorkday"],
                    "nwt": nwt_day["isWorkday"],
                    "tpe_category": tpe_day["category"],
                    "nwt_category": nwt_day["category"],
                }
            )
    if diffs:
        raise SourceMismatchError(year, diffs)
