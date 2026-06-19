# taiwan-work-calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將臺北市、新北市辦公日曆表 CSV 轉成每年 `data/YYYY.json`（全年逐日含 isWorkday），並以 GitHub Actions 於 7–12 月 1/15 日自動更新來年資料，來源不符時自動開 issue 中斷。

**Architecture:** 純 Python 套件 `taiwan_work_calendar`，模組各司其職：sources（下載/解析/驗欄位）、model（分類→isWorkday、組全年）、reconcile（交叉驗證）、builder（組單年 dict）、issues（開 issue 去重）、errors（中斷例外）、main（CLI 編排，先全驗證再全寫檔）。

**Tech Stack:** Python 3.12、uv、pytest、Python 標準函式庫（csv/json/datetime/urllib/argparse/logging），無第三方執行期相依。

## Global Constraints

- Python 版本下限：3.12；套件管理：uv。
- 執行期僅用標準函式庫；開發期相依：pytest。
- JSON 輸出：UTF-8、`ensure_ascii=False`、2 空白縮排、結尾換行、**不含變動時間戳**。
- 來源代碼：臺北 `tpe`、新北 `nwt`（小寫）。
- weekday 採 ISO 1–7（1=週一）。
- 預設只處理「來年」= 當前西元年 + 1；`--year` 可覆寫。
- 自動開 issue 僅三種：來源不一致、欄位/格式變動、未知分類。中斷時完全不寫檔。
- 容忍單一來源下載失敗；兩來源皆失敗才致命。
- Commit 用 Conventional Commits，含 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 程式註解、log 訊息、issue 內文使用繁體中文。

## File Structure

- `pyproject.toml` — uv 專案設定、pytest 設定。
- `taiwan_work_calendar/__init__.py` — 套件版本。
- `taiwan_work_calendar/errors.py` — 三種中斷例外，各帶 `issue_title()`/`issue_body()`。
- `taiwan_work_calendar/model.py` — 分類常數、`derive_is_workday`、`validate_categories`、`build_year_days`。
- `taiwan_work_calendar/sources.py` — URL/欄位常數、`parse_tpe`/`parse_nwt`、`download`、`fetch_tpe`/`fetch_nwt`。
- `taiwan_work_calendar/reconcile.py` — `reconcile_year`。
- `taiwan_work_calendar/builder.py` — `build_year`、`merge_records`。
- `taiwan_work_calendar/issues.py` — `GitHubIssueClient`、`report_error`。
- `taiwan_work_calendar/main.py` — `determine_target_years`、`run`、`main`、`write_year_file`。
- `tests/` — 對應每模組測試。
- `.github/workflows/update-calendar.yml` — 排程 workflow。
- `README.md` — 最後補。

---

### Task 1: 專案骨架（uv + pytest）

**Files:**
- Create: `pyproject.toml`
- Create: `taiwan_work_calendar/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: 可執行 `uv run pytest`；套件 `taiwan_work_calendar` 可匯入，`__version__` 字串。

- [ ] **Step 1: 寫 pyproject.toml**

```toml
[project]
name = "taiwan-work-calendar"
version = "0.1.0"
description = "臺灣辦公日曆表轉 JSON"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["taiwan_work_calendar"]
```

- [ ] **Step 2: 建立套件與測試骨架**

`taiwan_work_calendar/__init__.py`:
```python
"""臺灣辦公日曆表轉 JSON 套件。"""

__version__ = "0.1.0"
```

`tests/__init__.py`: 空檔。

`tests/test_smoke.py`:
```python
import taiwan_work_calendar


def test_package_has_version():
    assert isinstance(taiwan_work_calendar.__version__, str)
```

- [ ] **Step 3: 執行測試確認通過**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS（uv 會自動建立環境並安裝 pytest）

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml taiwan_work_calendar tests
git commit -m "chore: 初始化 uv 專案骨架與 pytest"
```

---

### Task 2: errors.py 中斷例外

**Files:**
- Create: `taiwan_work_calendar/errors.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Produces:
  - `CalendarError(Exception)` 基底。
  - `SchemaChangedError(source: str, expected: list[str], actual: list[str])`
  - `UnknownCategoryError(source: str, category: str, date: str)`
  - `SourceMismatchError(year: int, diffs: list[dict])`，diff 形如 `{"date","tpe","nwt","tpe_category","nwt_category"}`
  - 三者皆有 `issue_title() -> str` 與 `issue_body() -> str`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_errors.py`:
```python
from taiwan_work_calendar.errors import (
    SchemaChangedError,
    UnknownCategoryError,
    SourceMismatchError,
)


def test_schema_changed_issue_text():
    err = SchemaChangedError("nwt", ["a", "b"], ["a", "x"])
    assert "格式變動" in err.issue_title()
    assert "nwt" in err.issue_title()
    assert "a, b" in err.issue_body()
    assert "a, x" in err.issue_body()


def test_unknown_category_issue_text():
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    assert "未知分類" in err.issue_title()
    assert "颱風假" in err.issue_title()
    assert "20270815" in err.issue_body()


def test_source_mismatch_issue_text():
    diffs = [
        {"date": "2027-09-28", "tpe": True, "nwt": False,
         "tpe_category": "特定節日", "nwt_category": "放假之紀念日及節日"}
    ]
    err = SourceMismatchError(2027, diffs)
    assert "資料不一致" in err.issue_title()
    assert "2027" in err.issue_title()
    assert "2027-09-28" in err.issue_body()
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 errors.py**

```python
"""轉換流程的中斷例外；每種例外都能產生對應的 GitHub issue 標題與內文。"""


class CalendarError(Exception):
    """本專案所有可預期中斷例外的基底。"""

    def issue_title(self) -> str:  # pragma: no cover - 由子類覆寫
        raise NotImplementedError

    def issue_body(self) -> str:  # pragma: no cover - 由子類覆寫
        raise NotImplementedError


class SchemaChangedError(CalendarError):
    """來源 CSV 欄位與預期不符（來源改版）。"""

    def __init__(self, source: str, expected: list[str], actual: list[str]):
        self.source = source
        self.expected = expected
        self.actual = actual
        super().__init__(f"{source} 欄位不符：預期 {expected}，實際 {actual}")

    def issue_title(self) -> str:
        return f"[格式變動] 來源 {self.source} CSV 欄位與預期不符"

    def issue_body(self) -> str:
        return (
            f"來源 `{self.source}` 的 CSV 欄位與程式預期不符，請檢查來源是否改版並更新解析程式。\n\n"
            f"- 預期欄位：{', '.join(self.expected)}\n"
            f"- 實際欄位：{', '.join(self.actual)}\n"
        )


class UnknownCategoryError(CalendarError):
    """holidayCategory 出現程式未定義的分類，無法判斷是否上班。"""

    def __init__(self, source: str, category: str, date: str):
        self.source = source
        self.category = category
        self.date = date
        super().__init__(f"{source} 於 {date} 出現未知分類「{category}」")

    def issue_title(self) -> str:
        return f"[未知分類] 來源 {self.source} 出現未定義分類「{self.category}」"

    def issue_body(self) -> str:
        return (
            f"來源 `{self.source}` 出現程式未定義的分類，無法判斷該日是否上班，已中斷且未寫出任何檔案。\n\n"
            f"- 分類：{self.category}\n"
            f"- 首次出現日期：{self.date}\n\n"
            f"請於 `taiwan_work_calendar/model.py` 的分類集合中新增此分類並指定語意後重跑。\n"
        )


class SourceMismatchError(CalendarError):
    """兩來源對同一日期推導出的 isWorkday 不一致。"""

    def __init__(self, year: int, diffs: list[dict]):
        self.year = year
        self.diffs = diffs
        super().__init__(f"{year} 年兩來源 isWorkday 不一致，共 {len(diffs)} 筆")

    def issue_title(self) -> str:
        return f"[資料不一致] {self.year} 年 tpe/nwt 辦公日推導結果不符"

    def issue_body(self) -> str:
        lines = [
            f"`{self.year}` 年臺北（tpe）與新北（nwt）推導後的是否上班結果不一致，已中斷且未寫出任何檔案。\n",
            "| 日期 | tpe 上班 | nwt 上班 | tpe 分類 | nwt 分類 |",
            "|---|---|---|---|---|",
        ]
        for d in self.diffs:
            lines.append(
                f"| {d['date']} | {d['tpe']} | {d['nwt']} | "
                f"{d['tpe_category'] or '（無）'} | {d['nwt_category'] or '（無）'} |"
            )
        lines.append("\n請確認來源資料並修正程式或回報來源單位後重跑。")
        return "\n".join(lines)
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/errors.py tests/test_errors.py
git commit -m "feat: 新增中斷例外與 issue 文字產生"
```

---

### Task 3: model.py 分類規則與全年逐日

**Files:**
- Create: `taiwan_work_calendar/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `errors.UnknownCategoryError`。
- Produces:
  - 常數集合 `NON_WORKING_CATEGORIES`、`WORKING_CATEGORIES`、`INFO_ONLY_CATEGORIES`、`KNOWN_CATEGORIES`。
  - `derive_is_workday(d: datetime.date, category: str) -> bool`（category 空字串代表非特殊日）。
  - `validate_categories(source: str, records: dict[str, dict]) -> None`（未知分類 → `UnknownCategoryError`）。
  - `build_year_days(year: int, records: dict[str, dict]) -> list[dict]`（records 鍵為 `YYYYMMDD`，值含 `name`/`category`/`description`）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_model.py`:
```python
from datetime import date

import pytest

from taiwan_work_calendar import model
from taiwan_work_calendar.errors import UnknownCategoryError


def test_plain_weekday_is_workday():
    assert model.derive_is_workday(date(2027, 6, 16), "") is True  # 週三


def test_plain_weekend_is_holiday():
    assert model.derive_is_workday(date(2027, 6, 19), "") is False  # 週六


def test_off_categories_force_holiday():
    for cat in ["星期六、星期日", "放假之紀念日及節日", "補假", "調整放假日"]:
        assert model.derive_is_workday(date(2027, 6, 16), cat) is False


def test_makeup_workday_overrides_weekend():
    # 補行上班即使在週六也算上班
    assert model.derive_is_workday(date(2027, 6, 19), "補行上班") is True


def test_special_festival_does_not_override():
    # 特定節日（警察節）不覆蓋：週一仍上班
    assert model.derive_is_workday(date(2026, 6, 15), "特定節日") is True


def test_validate_categories_raises_on_unknown():
    records = {"20270815": {"name": "颱風假", "category": "颱風假", "description": ""}}
    with pytest.raises(UnknownCategoryError) as exc:
        model.validate_categories("tpe", records)
    assert exc.value.category == "颱風假"


def test_build_year_days_full_year_and_summary_fields():
    records = {
        "20270101": {"name": "中華民國開國紀念日", "category": "放假之紀念日及節日",
                     "description": "放假一日。"},
    }
    days = model.build_year_days(2027, records)
    assert len(days) == 365
    first = days[0]
    assert first["date"] == "2027-01-01"
    assert first["weekday"] == 5  # 2027-01-01 為週五
    assert first["isWorkday"] is False
    assert first["name"] == "中華民國開國紀念日"
    # 平日空白日
    plain = next(x for x in days if x["date"] == "2027-01-04")  # 週一
    assert plain["isWorkday"] is True
    assert plain["name"] == "" and plain["category"] == ""


def test_build_year_days_leap_year():
    assert len(model.build_year_days(2028, {})) == 366
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 model.py**

```python
"""辦公日曆的分類語意與全年逐日建構。

分類對「一般機關學校是否上班」的語意集中於此，作為唯一事實來源。
"""

from __future__ import annotations

from datetime import date, timedelta

from .errors import UnknownCategoryError

# 放假類：一般機關學校不上班
NON_WORKING_CATEGORIES = {
    "星期六、星期日",
    "放假之紀念日及節日",
    "補假",
    "調整放假日",
}

# 上班類：補行上班（補班），即使落在週末仍須上班
WORKING_CATEGORIES = {"補行上班"}

# 僅供參考類：職業別節日（如警察節），一般機關照常上班，不影響 isWorkday
INFO_ONLY_CATEGORIES = {"特定節日"}

KNOWN_CATEGORIES = (
    NON_WORKING_CATEGORIES | WORKING_CATEGORIES | INFO_ONLY_CATEGORIES
)


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
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/model.py tests/test_model.py
git commit -m "feat: 新增分類→isWorkday 規則與全年逐日建構"
```

---

### Task 4: sources.py 下載與解析

**Files:**
- Create: `taiwan_work_calendar/sources.py`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `errors.SchemaChangedError`。
- Produces:
  - 常數 `TPE_URL`、`NWT_URL`、`TPE_COLUMNS`、`NWT_COLUMNS`。
  - `parse_tpe(text: str) -> dict[str, dict]`、`parse_nwt(text: str) -> dict[str, dict]`（鍵 `YYYYMMDD`，值 `{name,category,description}`）。
  - `download(url: str) -> str`。
  - `fetch_tpe() -> dict`、`fetch_nwt() -> dict`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_sources.py`:
```python
import pytest

from taiwan_work_calendar import sources
from taiwan_work_calendar.errors import SchemaChangedError

TPE_SAMPLE = (
    "﻿Date,name,isHoliday,holidayCategory,description\n"
    "20260615,警察節,是,特定節日,警察依內政部規定辦理。\n"
    "20260619,端午節,是,放假之紀念日及節日,放假一日。\n"
)

NWT_SAMPLE = (
    '"date","year","name","isholiday","holidaycategory","description"\n'
    '"20260619","2026","端午節","是","放假之紀念日及節日","放假一日。"\n'
)


def test_parse_tpe_keys_and_values():
    rec = sources.parse_tpe(TPE_SAMPLE)
    assert set(rec) == {"20260615", "20260619"}
    assert rec["20260615"]["name"] == "警察節"
    assert rec["20260615"]["category"] == "特定節日"
    assert rec["20260619"]["description"] == "放假一日。"


def test_parse_nwt_keys_and_values():
    rec = sources.parse_nwt(NWT_SAMPLE)
    assert set(rec) == {"20260619"}
    assert rec["20260619"]["category"] == "放假之紀念日及節日"


def test_parse_tpe_schema_change_raises():
    bad = "Date,name,foo\n20260101,x,y\n"
    with pytest.raises(SchemaChangedError):
        sources.parse_tpe(bad)


def test_parse_nwt_schema_change_raises():
    bad = '"date","name"\n"20260101","x"\n'
    with pytest.raises(SchemaChangedError):
        sources.parse_nwt(bad)
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_sources.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 sources.py**

```python
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
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_sources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/sources.py tests/test_sources.py
git commit -m "feat: 新增來源下載與 CSV 解析（含欄位驗證）"
```

---

### Task 5: reconcile.py 交叉驗證

**Files:**
- Create: `taiwan_work_calendar/reconcile.py`
- Test: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `model.build_year_days`、`errors.SourceMismatchError`。
- Produces: `reconcile_year(year: int, tpe_records: dict, nwt_records: dict) -> None`（不一致 → `SourceMismatchError`）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_reconcile.py`:
```python
import pytest

from taiwan_work_calendar import reconcile
from taiwan_work_calendar.errors import SourceMismatchError


def test_police_day_not_treated_as_mismatch():
    # tpe 有警察節（特定節日，週一），nwt 無；兩者推導皆為上班 → 不應報錯
    tpe = {"20260615": {"name": "警察節", "category": "特定節日", "description": ""}}
    nwt = {}
    reconcile.reconcile_year(2026, tpe, nwt)  # 不拋例外即通過


def test_detects_workday_mismatch():
    # tpe 把某週六標補行上班（上班），nwt 無（週六放假）→ 不一致
    tpe = {"20260613": {"name": "", "category": "補行上班", "description": ""}}
    nwt = {}
    with pytest.raises(SourceMismatchError) as exc:
        reconcile.reconcile_year(2026, tpe, nwt)
    diffs = exc.value.diffs
    assert len(diffs) == 1
    assert diffs[0]["date"] == "2026-06-13"
    assert diffs[0]["tpe"] is True
    assert diffs[0]["nwt"] is False
    assert diffs[0]["tpe_category"] == "補行上班"
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 reconcile.py**

```python
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
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/reconcile.py tests/test_reconcile.py
git commit -m "feat: 新增兩來源 isWorkday 逐日交叉驗證"
```

---

### Task 6: builder.py 單年組裝

**Files:**
- Create: `taiwan_work_calendar/builder.py`
- Test: `tests/test_builder.py`

**Interfaces:**
- Consumes: `model.build_year_days`。
- Produces:
  - `merge_records(tpe_records: dict, nwt_records: dict) -> dict`（tpe 優先覆蓋，含 tpe 獨有日如警察節）。
  - `build_year(year: int, records: dict, sources: list[str]) -> dict`（回傳含 year/sources/summary/days 的 dict）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_builder.py`:
```python
from taiwan_work_calendar import builder


def test_build_year_structure_and_summary():
    records = {
        "20270101": {"name": "中華民國開國紀念日", "category": "放假之紀念日及節日",
                     "description": "放假一日。"},
    }
    result = builder.build_year(2027, records, ["tpe", "nwt"])
    assert result["year"] == 2027
    assert result["sources"] == ["tpe", "nwt"]
    assert result["summary"]["total"] == 365
    assert (result["summary"]["workdays"] + result["summary"]["holidays"]
            == result["summary"]["total"])
    assert len(result["days"]) == 365
    assert result["days"][0]["isWorkday"] is False


def test_merge_records_prefers_tpe_and_includes_tpe_only():
    tpe = {"20260615": {"name": "警察節", "category": "特定節日", "description": "a"}}
    nwt = {"20260619": {"name": "端午節", "category": "放假之紀念日及節日", "description": "b"}}
    merged = builder.merge_records(tpe, nwt)
    assert set(merged) == {"20260615", "20260619"}
    assert merged["20260615"]["name"] == "警察節"
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_builder.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 builder.py**

```python
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
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/builder.py tests/test_builder.py
git commit -m "feat: 新增單年結構組裝與來源記錄合併"
```

---

### Task 7: issues.py 開 issue 與去重

**Files:**
- Create: `taiwan_work_calendar/issues.py`
- Test: `tests/test_issues.py`

**Interfaces:**
- Consumes: `errors.CalendarError`（具 `issue_title()`/`issue_body()`）。
- Produces:
  - `GitHubIssueClient(token: str, repo: str)`，方法 `find_open_issue(title) -> bool`、`create_issue(title, body, labels) -> None`。
  - `report_error(error, *, client=None) -> None`：client 為 None 時僅記 log；已存在同標題 open issue 則不重開。

- [ ] **Step 1: 寫失敗測試**

`tests/test_issues.py`:
```python
from taiwan_work_calendar import issues
from taiwan_work_calendar.errors import UnknownCategoryError


class FakeClient:
    def __init__(self, existing=False):
        self.existing = existing
        self.created = []

    def find_open_issue(self, title):
        return self.existing

    def create_issue(self, title, body, labels):
        self.created.append((title, body, labels))


def test_report_error_creates_issue_when_absent():
    client = FakeClient(existing=False)
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=client)
    assert len(client.created) == 1
    assert client.created[0][0] == err.issue_title()
    assert "data-issue" in client.created[0][2]


def test_report_error_skips_duplicate():
    client = FakeClient(existing=True)
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=client)
    assert client.created == []


def test_report_error_without_client_does_not_raise():
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=None)  # 不應拋例外
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_issues.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 issues.py**

```python
"""透過 GitHub REST API 建立 issue，並以標題去重避免每月重複開啟。"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_LABEL = "data-issue"
_TIMEOUT = 30


class GitHubIssueClient:
    """最小化的 GitHub issue 用戶端（僅查詢 open issue 與建立 issue）。"""

    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo  # 形如 "owner/name"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "taiwan-work-calendar",
        }

    def find_open_issue(self, title: str) -> bool:
        """以 GitHub search API 判斷是否已有同標題的 open issue。"""
        query = f'repo:{self.repo} is:issue is:open in:title "{title}"'
        url = f"{_API}/search/issues?q={urllib.parse.quote(query)}"
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        for item in data.get("items", []):
            if item.get("title") == title:
                return True
        return False

    def create_issue(self, title: str, body: str, labels: list[str]) -> None:
        url = f"{_API}/repos/{self.repo}/issues"
        payload = json.dumps(
            {"title": title, "body": body, "labels": labels}
        ).encode("utf-8")
        request = urllib.request.Request(
            url, data=payload, headers=self._headers(), method="POST"
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            response.read()


def client_from_env() -> GitHubIssueClient | None:
    """於 GitHub Actions 環境（有 GITHUB_TOKEN 與 GITHUB_REPOSITORY）時建立 client。"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if token and repo:
        return GitHubIssueClient(token, repo)
    return None


def report_error(error, *, client: GitHubIssueClient | None = None) -> None:
    """依例外開立 issue；無 client 僅記 log，已存在同標題則不重開。"""
    title = error.issue_title()
    body = error.issue_body()
    if client is None:
        logger.warning("未設定 GitHub client，略過開立 issue：%s", title)
        return
    if client.find_open_issue(title):
        logger.info("已存在相同 issue，略過建立：%s", title)
        return
    client.create_issue(title, body, [_LABEL])
    logger.info("已建立 issue：%s", title)
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_issues.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add taiwan_work_calendar/issues.py tests/test_issues.py
git commit -m "feat: 新增 GitHub issue 建立與標題去重"
```

---

### Task 8: main.py CLI 與流程編排

**Files:**
- Create: `taiwan_work_calendar/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: 全部模組。
- Produces:
  - `determine_target_years(year_arg: str | None, today: datetime.date) -> list[int]`。
  - `write_year_file(data_dir: pathlib.Path, year_data: dict) -> pathlib.Path`。
  - `run(argv: list[str] | None = None, *, today=None, fetchers=None, client=None) -> int`（回傳退出碼；`fetchers` 為 `{"tpe": callable, "nwt": callable}` 以利測試注入）。
  - `main() -> None`（設定 logging 後呼叫 run，並 `sys.exit`）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_main.py`:
```python
import json
from datetime import date

from taiwan_work_calendar import main


def test_determine_target_years_default_is_next_year():
    assert main.determine_target_years(None, date(2026, 7, 1)) == [2027]


def test_determine_target_years_explicit_single():
    assert main.determine_target_years("2025", date(2026, 7, 1)) == [2025]


def test_determine_target_years_explicit_multiple_sorted_unique():
    assert main.determine_target_years("2027,2025,2025", date(2026, 1, 1)) == [2025, 2027]


def _records_for_year(year, extra=None):
    # 提供整年週末，避免單來源時資料不足；此處僅放一筆放假日即可（其餘平日由程式補）
    rec = {f"{year}0101": {"name": "元旦", "category": "放假之紀念日及節日", "description": ""}}
    if extra:
        rec.update(extra)
    return rec


def test_run_writes_next_year_file(tmp_path):
    fetchers = {
        "tpe": lambda: _records_for_year(2027),
        "nwt": lambda: _records_for_year(2027),
    }
    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers=fetchers,
        client=None,
    )
    assert code == 0
    out = tmp_path / "2027.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["year"] == 2027
    assert data["sources"] == ["tpe", "nwt"]


def test_run_single_source_when_one_fails(tmp_path):
    def boom():
        raise RuntimeError("nwt 下載失敗")

    fetchers = {
        "tpe": lambda: _records_for_year(2027),
        "nwt": boom,
    }
    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers=fetchers,
        client=None,
    )
    assert code == 0
    data = json.loads((tmp_path / "2027.json").read_text(encoding="utf-8"))
    assert data["sources"] == ["tpe"]


def test_run_soft_skip_when_year_not_published(tmp_path):
    fetchers = {
        "tpe": lambda: _records_for_year(2026),  # 沒有 2027
        "nwt": lambda: _records_for_year(2026),
    }
    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers=fetchers,
        client=None,
    )
    assert code == 0
    assert not (tmp_path / "2027.json").exists()


def test_run_halts_and_reports_on_mismatch(tmp_path):
    # tpe 把 2027-09-25(週六) 標補行上班、nwt 無 → 不一致 → 中斷不寫檔
    tpe = _records_for_year(2027, {"20270925": {"name": "", "category": "補行上班", "description": ""}})
    nwt = _records_for_year(2027)
    created = []

    class FakeClient:
        def find_open_issue(self, title):
            return False

        def create_issue(self, title, body, labels):
            created.append(title)

    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers={"tpe": lambda: tpe, "nwt": lambda: nwt},
        client=FakeClient(),
    )
    assert code == 1
    assert not (tmp_path / "2027.json").exists()
    assert any("資料不一致" in t for t in created)


def test_run_fatal_when_both_sources_fail(tmp_path):
    def boom():
        raise RuntimeError("壞了")

    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers={"tpe": boom, "nwt": boom},
        client=None,
    )
    assert code == 1
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 實作 main.py**

```python
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
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: 全測試 + 註冊 console script**

在 `pyproject.toml` 的 `[project]` 後新增：
```toml
[project.scripts]
twcal = "taiwan_work_calendar.main:main"
```
Run: `uv run pytest -v`
Expected: 全數 PASS

- [ ] **Step 6: Commit**

```bash
git add taiwan_work_calendar/main.py tests/test_main.py pyproject.toml
git commit -m "feat: 新增 CLI 與流程編排（先全驗證再全寫檔）"
```

---

### Task 9: 用真實資料產生當前年份並驗證

**Files:**
- Create: `data/2026.json`（實跑產出）

**Interfaces:**
- Consumes: 完整 CLI。

- [ ] **Step 1: 以真實來源產生 2026（手動指定年份）**

Run: `uv run twcal --year 2026`
Expected: 寫出 `data/2026.json`，log 顯示兩來源成功與上班/放假天數。

- [ ] **Step 2: 健全性檢查**

Run:
```bash
uv run python -c "import json;d=json.load(open('data/2026.json'));print(d['year'],d['sources'],d['summary']);assert d['summary']['total']==365;assert len(d['days'])==365;assert d['summary']['workdays']+d['summary']['holidays']==365;print('OK')"
```
Expected: 印出 summary 與 `OK`；sources 為 `['tpe','nwt']`。

- [ ] **Step 3: 抽查警察節（不誤判）**

Run:
```bash
uv run python -c "import json;d=json.load(open('data/2026.json'));x=[v for v in d['days'] if v['date']=='2026-06-15'][0];print(x);assert x['isWorkday'] is True"
```
Expected: 6/15 警察節 `isWorkday=True`。

- [ ] **Step 4: Commit**

```bash
git add data/2026.json
git commit -m "feat: 產生 2026 年辦公日曆表 JSON"
```

---

### Task 10: GitHub Actions 排程 workflow

**Files:**
- Create: `.github/workflows/update-calendar.yml`

**Interfaces:**
- Consumes: `uv run twcal`。

- [ ] **Step 1: 寫 workflow**

`.github/workflows/update-calendar.yml`:
```yaml
name: 更新辦公日曆表

on:
  schedule:
    # UTC 0 點＝臺灣 8 點；每年 7–12 月的 1 日與 15 日
    - cron: "0 0 1,15 7-12 *"
  workflow_dispatch:
    inputs:
      year:
        description: "指定年份（逗號分隔），留空為來年"
        required: false
        default: ""

permissions:
  contents: write
  issues: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: 取出程式碼
        uses: actions/checkout@v4

      - name: 安裝 uv
        uses: astral-sh/setup-uv@v5

      - name: 執行轉換
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          if [ -n "${{ github.event.inputs.year }}" ]; then
            uv run twcal --year "${{ github.event.inputs.year }}"
          else
            uv run twcal
          fi

      - name: 提交變更（若有）
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if [ -n "$(git status --porcelain data/)" ]; then
            git add data/
            git commit -m "chore(data): 自動更新辦公日曆表 JSON"
            git push
          else
            echo "資料無變更，略過提交。"
          fi
```

- [ ] **Step 2: 驗證 YAML 可解析**

Run: `uv run python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/update-calendar.yml'))" 2>/dev/null || python3 -c "import json;print('改用基本檢查')"`
Expected: 無錯誤（若無 pyyaml 則略過，YAML 內容以人工核對縮排）。

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/update-calendar.yml
git commit -m "ci: 新增 7-12 月 1/15 日自動更新 workflow"
```

---

### Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 寫 README**（涵蓋：用途、資料來源與代碼、JSON 格式說明與範例、分類規則表、本機執行方式 `uv run twcal [--year]`、自動更新排程說明、來源不符時的 issue 機制）。內容以繁體中文撰寫，避免 emoji。

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: 新增 README 使用說明"
```

---

## Self-Review

**Spec coverage：**
- 資料來源/代碼（tpe/nwt）→ Task 4、README。
- 全年逐日 JSON 格式 → Task 3、6、9。
- 分類→isWorkday（含特定節日/補行上班）→ Task 3。
- 預設只處理來年、可覆寫 → Task 8。
- 兩來源比對推導 isWorkday、不符開 issue 中斷不寫檔 → Task 5、7、8。
- 容忍單一來源失敗、兩者皆失敗致命 → Task 8。
- 未發布來年 soft-skip → Task 8。
- 三種 issue 觸發（不一致/格式/未知分類）→ Task 2、4、3 + 8 編排。
- GitHub Actions 7–12 月 1/15 日 → Task 10。
- README → Task 11。

**Placeholder scan：** 無 TBD/TODO；所有程式步驟含完整程式碼。

**Type consistency：** records 一律 `dict[YYYYMMDD] -> {name,category,description}`；diffs 鍵 `date/tpe/nwt/tpe_category/nwt_category` 於 errors/reconcile/test 一致；`build_year` 回傳鍵與測試一致。

無缺漏。
