"""來源歧異的人工覆寫設定。

當兩來源對某日期的 isWorkday 推導不一致時，預設會開 issue 並中斷。
開發者可於 overrides.json 指定該日期信任哪個來源，使後續執行自動解決該歧異，
無需改動程式碼。

overrides.json 格式（鍵為 YYYY-MM-DD）：
{
  "2026-05-01": { "trust": "tpe", "reason": "說明文字" }
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_overrides(path: Path) -> dict[str, dict]:
    """讀取覆寫設定；檔案不存在則回傳空 dict。"""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"overrides 檔案格式須為物件：{path}")
    return data


def apply_overrides_to_records(
    records: dict, have: dict, overrides: dict
) -> dict:
    """依覆寫設定，將指定日期改採被信任來源的記錄。

    - records：合併後（預設）記錄，鍵為 YYYYMMDD。
    - have：本年實際可用的各來源記錄，{來源代碼: {YYYYMMDD: rec}}。
    - overrides：{YYYY-MM-DD: {"trust": 來源代碼, ...}}。

    被信任來源若有該日特殊日記錄則採用；若無（代表該來源視為平日）則移除，
    使後續推導回到平日基準。
    """
    result = dict(records)
    for date_str, override in overrides.items():
        key = date_str.replace("-", "")
        trust = override.get("trust")
        if trust not in have:
            continue
        trusted = have[trust]
        if key in trusted:
            result[key] = trusted[key]
            logger.info("套用來源覆寫：%s 採用 %s", date_str, trust)
        elif key in result:
            del result[key]
            logger.info("套用來源覆寫：%s 採用 %s（視為平日）", date_str, trust)
    return result
