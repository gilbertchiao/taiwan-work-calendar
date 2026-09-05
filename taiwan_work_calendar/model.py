"""辦公日曆的分類語意與全年逐日建構。

分類對「一般機關學校是否上班」的語意集中於此，作為唯一事實來源。
"""

from __future__ import annotations

from datetime import date, timedelta

from .errors import UnknownCategoryError

# 放假類：一般機關學校不上班
NON_WORKING_CATEGORIES = {
    "星期六、星期日",
    "星期日",  # 部分舊資料單獨標示週日
    "放假之紀念日及節日",
    "補假",
    "調整放假日",
}

# 上班類：補行上班（補班），即使落在週末仍須上班；舊資料用「補行上班日」
WORKING_CATEGORIES = {"補行上班", "補行上班日"}

# 僅供參考類：一般機關照常上班、不影響 isWorkday（依基準週一～五）。
# 含職業別節日（如警察節、勞動節）與無「放假之」前綴的紀念日及節日（如婦女節、教師節）。
INFO_ONLY_CATEGORIES = {"特定節日", "紀念日及節日"}

KNOWN_CATEGORIES = NON_WORKING_CATEGORIES | WORKING_CATEGORIES | INFO_ONLY_CATEGORIES


def derive_is_workday(d: date, category: str) -> bool:
    """依日期與分類推導一般機關學校當日是否上班。

    category 為空字串代表該日非來源特殊日（一般平日/週末）。
    呼叫前應已用 validate_categories 確認分類皆已知。
    """
    base = d.weekday() < 5  # 週一=0 … 週五=4 為上班基準
    if not category:
        return base
    if category in NON_WORKING_CATEGORIES:
        return False
    if category in WORKING_CATEGORIES:
        return True
    if category in INFO_ONLY_CATEGORIES:
        return base
    # 理論上不會到這（已先 validate），保留防禦性處理
    raise ValueError(f"未知分類：{category}")


def validate_categories(source: str, records: dict[str, dict]) -> None:
    """檢查所有分類是否皆已定義；遇未知分類即拋例外（附首次出現日期）。"""
    for date_str in sorted(records):
        category = records[date_str]["category"]
        if category and category not in KNOWN_CATEGORIES:
            raise UnknownCategoryError(source, category, date_str)


def build_year_days(year: int, records: dict[str, dict]) -> list[dict]:
    """產生該年 1/1～12/31 的逐日清單。"""
    days: list[dict] = []
    current = date(year, 1, 1)
    while current.year == year:
        key = current.strftime("%Y%m%d")
        record = records.get(key)
        category = record["category"] if record else ""
        days.append(
            {
                "date": current.isoformat(),
                "weekday": current.isoweekday(),
                "isWorkday": derive_is_workday(current, category),
                "name": record["name"] if record else "",
                "category": category,
                "description": record["description"] if record else "",
            }
        )
        current += timedelta(days=1)
    return days
