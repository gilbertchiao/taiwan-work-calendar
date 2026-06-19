"""來源 CSV 的下載與解析。

兩來源僅列「特殊日」（週末/放假/補班），平日不列。
解析後正規化為 dict[YYYYMMDD] -> {name, category, description}。
"""

from __future__ import annotations

import csv
import io
import urllib.request

from .errors import SchemaChangedError

TPE_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=0dcbcfcf-f7a1-4664-a810-82c01cb524e0"
)
NWT_URL = (
    "https://data.ntpc.gov.tw/api/datasets/"
    "308dcd75-6434-45bc-a95f-584da4fed251/csv?page=0&size=10000"
)

TPE_COLUMNS = ["Date", "name", "isHoliday", "holidayCategory", "description"]
NWT_COLUMNS = ["date", "year", "name", "isholiday", "holidaycategory", "description"]

_TIMEOUT = 30


def _parse(text: str, source: str, expected: list[str], field_map: dict[str, str]) -> dict[str, dict]:
    """共用解析：驗證欄位後逐列轉成正規化記錄。

    field_map 將「正規化鍵」對應到「CSV 欄位名」：date/name/category/description。
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise SchemaChangedError(source, expected, [])
    # 去除 UTF-8 BOM
    if header and header[0].startswith("﻿"):
        header[0] = header[0].lstrip("﻿")
    if header != expected:
        raise SchemaChangedError(source, expected, header)

    index = {name: pos for pos, name in enumerate(header)}
    records: dict[str, dict] = {}
    for row in reader:
        if not row or len(row) < len(expected):
            continue
        date_str = row[index[field_map["date"]]].strip()
        if not date_str:
            continue
        records[date_str] = {
            "name": row[index[field_map["name"]]].strip(),
            "category": row[index[field_map["category"]]].strip(),
            "description": row[index[field_map["description"]]].strip(),
        }
    return records


def parse_tpe(text: str) -> dict[str, dict]:
    return _parse(
        text,
        "tpe",
        TPE_COLUMNS,
        {"date": "Date", "name": "name", "category": "holidayCategory",
         "description": "description"},
    )


def parse_nwt(text: str) -> dict[str, dict]:
    return _parse(
        text,
        "nwt",
        NWT_COLUMNS,
        {"date": "date", "name": "name", "category": "holidaycategory",
         "description": "description"},
    )


def download(url: str) -> str:
    """下載 URL 內容並以 UTF-8 解碼。"""
    request = urllib.request.Request(url, headers={"User-Agent": "taiwan-work-calendar"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return response.read().decode("utf-8-sig")


def fetch_tpe() -> dict[str, dict]:
    return parse_tpe(download(TPE_URL))


def fetch_nwt() -> dict[str, dict]:
    return parse_nwt(download(NWT_URL))
