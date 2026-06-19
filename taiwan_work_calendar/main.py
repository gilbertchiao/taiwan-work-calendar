"""CLI 進入點與流程編排：先全驗證、再全寫檔。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from . import sources
from .builder import build_year, merge_records
from .errors import CalendarError
from .issues import client_from_env, report_error
from .model import validate_categories
from .reconcile import reconcile_year

logger = logging.getLogger(__name__)


def determine_target_years(year_arg: str | None, today: date) -> list[int]:
    """決定目標年份：預設為來年；可用逗號分隔字串覆寫。"""
    if year_arg:
        years = {int(part) for part in year_arg.split(",") if part.strip()}
        return sorted(years)
    return [today.year + 1]


def _records_have_year(records: dict, year: int) -> bool:
    prefix = str(year)
    return any(key.startswith(prefix) for key in records)


def write_year_file(data_dir: Path, year_data: dict) -> Path:
    """寫出單年 JSON（UTF-8、不轉義中文、2 空白縮排、結尾換行）。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{year_data['year']}.json"
    text = json.dumps(year_data, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _fetch_all(fetchers: dict) -> dict:
    """嘗試下載各來源；容忍單一失敗，回傳成功者。"""
    available = {}
    for code, fetch in fetchers.items():
        try:
            available[code] = fetch()
            logger.info("來源 %s 下載成功（%d 筆特殊日）", code, len(available[code]))
        except Exception as exc:  # 下載/解析失敗：記錄後續行
            logger.warning("來源 %s 取得失敗：%s", code, exc)
    return available


def _plan_year(year: int, available: dict):
    """回傳 (records, sources) 或 None（該年尚未發布）。會做分類驗證與交叉比對。"""
    have = {c: r for c, r in available.items() if _records_have_year(r, year)}
    if not have:
        logger.info("%d 年來源尚未發布，略過。", year)
        return None
    for code, records in have.items():
        validate_categories(code, records)
    if "tpe" in have and "nwt" in have:
        reconcile_year(year, have["tpe"], have["nwt"])
        records = merge_records(have["tpe"], have["nwt"])
        return records, ["tpe", "nwt"]
    code, records = next(iter(have.items()))
    return records, [code]


def run(argv=None, *, today=None, fetchers=None, client=None) -> int:
    """執行轉換流程，回傳退出碼。"""
    parser = argparse.ArgumentParser(description="臺灣辦公日曆表轉 JSON")
    parser.add_argument("--year", help="指定年份（逗號分隔），預設為來年")
    parser.add_argument("--data-dir", default="data", help="輸出目錄，預設 data")
    args = parser.parse_args(argv)

    today = today or date.today()
    fetchers = fetchers or {"tpe": sources.fetch_tpe, "nwt": sources.fetch_nwt}
    target_years = determine_target_years(args.year, today)
    logger.info("目標年份：%s", target_years)

    available = _fetch_all(fetchers)
    if not available:
        logger.error("所有來源皆下載失敗，無法繼續。")
        return 1

    # 先全驗證：任一中斷例外即開 issue 並完全不寫檔
    plans = {}
    try:
        for year in target_years:
            plan = _plan_year(year, available)
            if plan is not None:
                plans[year] = plan
    except CalendarError as exc:
        logger.error("驗證失敗，將開立 issue 並中斷（不寫檔）：%s", exc)
        report_error(exc, client=client)
        return 1

    if not plans:
        logger.info("沒有可產出的年份（皆尚未發布），正常結束。")
        return 0

    # 全部通過才寫檔
    data_dir = Path(args.data_dir)
    for year, (records, src) in plans.items():
        year_data = build_year(year, records, src)
        path = write_year_file(data_dir, year_data)
        logger.info("已寫出 %s（上班 %d 天 / 放假 %d 天）",
                    path, year_data["summary"]["workdays"],
                    year_data["summary"]["holidays"])
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    client = client_from_env()
    sys.exit(run(client=client))


if __name__ == "__main__":
    main()
