"""驗證 data/YYYY.json 是否符合 schema 與內部一致性。

用法：python scripts/validate_data.py [data_dir]

除了 JSON Schema 結構檢查外，另做 schema 無法表達的語意檢查：
- 檔名年份與內容 year 一致
- days 涵蓋該年每一天、依日期排序、無重複
- weekday 與實際日期相符
- summary 的 total / workdays / holidays 與 days 統計一致
任一檔案失敗即以非零退出碼結束，供 CI 使用。
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "calendar.schema.json"
FILENAME_RE = re.compile(r"^(\d{4})\.json$")


def _expected_dates(year: int) -> list[str]:
    start = date(year, 1, 1)
    days = 366 if calendar.isleap(year) else 365
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def check_file(path: Path, validator: Draft202012Validator) -> list[str]:
    """回傳該檔案的所有錯誤訊息；空 list 代表通過。"""
    errors: list[str] = []
    match = FILENAME_RE.match(path.name)
    if not match:
        return [f"檔名不符 YYYY.json 格式：{path.name}"]
    file_year = int(match.group(1))

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"無法讀取或解析 JSON：{exc}"]

    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in err.path) or "<root>"
        errors.append(f"schema：{location}：{err.message}")
    if errors:
        return errors  # 結構不對時後續語意檢查沒有意義

    if data["year"] != file_year:
        errors.append(f"year 欄位 {data['year']} 與檔名年份 {file_year} 不一致")

    dates = [d["date"] for d in data["days"]]
    expected = _expected_dates(file_year)
    if dates != expected:
        missing = sorted(set(expected) - set(dates))
        extra = sorted(set(dates) - set(expected))
        errors.append(
            f"days 未涵蓋全年或順序有誤（缺 {len(missing)} 天、多 {len(extra)} 天，"
            f"例：缺 {missing[:3]}，多 {extra[:3]}）"
        )

    for day in data["days"]:
        actual_weekday = date.fromisoformat(day["date"]).isoweekday()
        if day["weekday"] != actual_weekday:
            errors.append(f"{day['date']} weekday 應為 {actual_weekday}，實際為 {day['weekday']}")

    workdays = sum(1 for d in data["days"] if d["isWorkday"])
    holidays = len(data["days"]) - workdays
    summary = data["summary"]
    if (summary["total"], summary["workdays"], summary["holidays"]) != (
        len(data["days"]),
        workdays,
        holidays,
    ):
        errors.append(
            f"summary {summary} 與 days 統計不符"
            f"（total={len(data['days'])}, workdays={workdays}, holidays={holidays}）"
        )
    return errors


def main(argv: list[str]) -> int:
    data_dir = Path(argv[1]) if len(argv) > 1 else ROOT / "data"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    files = sorted(p for p in data_dir.glob("*.json") if FILENAME_RE.match(p.name))
    if not files:
        print(f"[WARN] {data_dir} 內沒有 YYYY.json，略過驗證。")
        return 0

    failed = 0
    for path in files:
        errors = check_file(path, validator)
        if errors:
            failed += 1
            print(f"[FAIL] {path.name}")
            for message in errors:
                print(f"       - {message}")
        else:
            print(f"[OK]   {path.name}")

    print(f"\n共 {len(files)} 檔，通過 {len(files) - failed}，失敗 {failed}。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
