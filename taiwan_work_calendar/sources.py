"""來源 CSV 的下載與解析。

兩來源僅列「特殊日」（週末/放假/補班），平日不列。
解析後正規化為 dict[YYYYMMDD] -> {name, category, description}。
"""

from __future__ import annotations

import csv
import io
import logging
import time
import urllib.request

from .errors import SchemaChangedError

logger = logging.getLogger(__name__)

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
# 下載重試：政府開放資料平台偶有瞬時錯誤，重試可避免退化成單一來源產出。
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # 秒；指數退避 2 → 4 → …


def _parse(
    text: str, source: str, expected: list[str], field_map: dict[str, str]
) -> dict[str, dict]:
    """共用解析：驗證欄位後逐列轉成正規化記錄。

    field_map 將「正規化鍵」對應到「CSV 欄位名」：date/name/category/description。
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise SchemaChangedError(source, expected, []) from None
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
        {
            "date": "Date",
            "name": "name",
            "category": "holidayCategory",
            "description": "description",
        },
    )


def parse_nwt(text: str) -> dict[str, dict]:
    return _parse(
        text,
        "nwt",
        NWT_COLUMNS,
        {
            "date": "date",
            "name": "name",
            "category": "holidaycategory",
            "description": "description",
        },
    )


def _open_url(url: str) -> str:
    """單次下載 URL 內容並以 UTF-8 解碼（分離出來以便測試替換）。"""
    request = urllib.request.Request(url, headers={"User-Agent": "taiwan-work-calendar"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return response.read().decode("utf-8-sig")


def download(url: str) -> str:
    """下載 URL 內容，失敗時以指數退避重試最多 _MAX_ATTEMPTS 次。

    最後一次仍失敗則原樣拋出例外，由呼叫端決定如何處理。
    """
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return _open_url(url)
        except Exception as exc:
            if attempt == _MAX_ATTEMPTS:
                logger.error("下載失敗（已重試 %d 次）：%s：%s", attempt, url, exc)
                raise
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "下載失敗（第 %d/%d 次），%.0f 秒後重試：%s：%s",
                attempt,
                _MAX_ATTEMPTS,
                delay,
                url,
                exc,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # 迴圈必定 return 或 raise


def fetch_tpe() -> dict[str, dict]:
    return parse_tpe(download(TPE_URL))


def fetch_nwt() -> dict[str, dict]:
    return parse_nwt(download(NWT_URL))
