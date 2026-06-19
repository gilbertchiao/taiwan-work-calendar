"""兩來源逐日比對推導後的 isWorkday。"""

from __future__ import annotations

from .errors import SourceMismatchError
from .model import build_year_days


def reconcile_year(
    year: int,
    tpe_records: dict,
    nwt_records: dict,
    overrides: dict | None = None,
) -> None:
    """比對兩來源該年每日 isWorkday，不一致則拋 SourceMismatchError。

    overrides 中已指定信任來源的日期視為已解決，不列入不一致。
    """
    overrides = overrides or {}
    tpe_days = {d["date"]: d for d in build_year_days(year, tpe_records)}
    nwt_days = {d["date"]: d for d in build_year_days(year, nwt_records)}

    diffs: list[dict] = []
    for date_str in sorted(tpe_days):
        if date_str in overrides:
            continue
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
