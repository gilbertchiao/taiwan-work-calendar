# 臺灣辦公日曆表 JSON 轉換專案 — 設計文件

- 文件日期：2026-06-19
- 專案名稱：taiwan-work-calendar
- 狀態：設計已確認，待寫實作計畫

## 1. 目標與背景

臺灣行政院人事行政總處每年上半年公告來年「辦公日曆表」，但僅以文件、圖檔呈現，不利程式介接。臺北市政府與新北市政府的開放資料平台提供結構化（CSV）的辦公日曆表，本專案以此兩者為資料來源，將每年辦公日曆表轉換成 JSON，方便程式判斷「某日是否上班」。

### 資料來源

| 代碼 | 機關 | 下載網址 | 涵蓋年份（實測 2026-06）|
|---|---|---|---|
| `tpe` | 臺北市政府 | `https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=0dcbcfcf-f7a1-4664-a810-82c01cb524e0` | 2013–2026 |
| `nwt` | 新北市政府 | `https://data.ntpc.gov.tw/api/datasets/308dcd75-6434-45bc-a95f-584da4fed251/csv?page=0&size=10000` | 2017–2026 |

> 代碼採 ISO 3166-2:TW 地區碼：臺北市 TPE → `tpe`、新北市 NWT → `nwt`（檔案內統一小寫）。

### 來源格式（實測）

兩來源皆為 CSV，**只列「特殊日」**（週末、放假日、補班日），平日不列。

- `tpe`：UTF-8 (BOM)，欄位 `Date,name,isHoliday,holidayCategory,description`
- `nwt`：UTF-8，欄位 `date,year,name,isholiday,holidaycategory,description`（多一個 `year` 欄）

範例列（tpe）：`20260615,警察節,是,特定節日,警察依內政部規定辦理。`

### 一致性實測結論

2017–2026 兩來源重疊年份近乎完全一致，唯一差異為 `2026-06-15 警察節`（分類「特定節日」）：`tpe` 有、`nwt` 無。此為**職業別節日**（警察依規定放假），一般機關學校照常上班，故 `nwt` 略過。此差異正是「以推導後 isWorkday 比對」能避免誤判的依據（見 §4）。

## 2. 核心需求（已與使用者確認）

1. 輸出粒度：**全年逐日**（每日一筆，含 isWorkday）。
2. 年份範圍預設：**只處理「來年」**。在 N 年執行只產生 `data/(N+1).json`，不異動其他年份。可用 CLI 指定年份覆寫。
3. 兩來源比對基準：**比對推導後的 isWorkday**（非原始欄位）。不一致 → 自動開 issue 並中斷。
4. 中斷範圍：任一需開 issue 的狀況發生時，**完全不寫檔**（整批中斷）。
5. 自動開 issue 的觸發條件僅三種：(a) 兩來源 isWorkday 不一致、(b) CSV 欄位/格式變動、(c) 出現未知 holidayCategory。
6. 容忍單一來源異常：只要有一個來源可用即照常執行；兩來源都失敗才視為致命錯誤。
7. 部署：GitHub Actions，每年 7–12 月的 1 日與 15 日自動執行。
8. README 於實作完成後補上。

## 3. 輸出格式 `data/YYYY.json`

```json
{
  "year": 2026,
  "sources": ["tpe", "nwt"],
  "summary": { "total": 365, "workdays": 248, "holidays": 117 },
  "days": [
    {
      "date": "2026-06-15",
      "weekday": 1,
      "isWorkday": true,
      "name": "警察節",
      "category": "特定節日",
      "description": "警察依內政部規定辦理。"
    },
    {
      "date": "2026-06-16",
      "weekday": 2,
      "isWorkday": true,
      "name": "",
      "category": "",
      "description": ""
    }
  ]
}
```

欄位定義：

- `year`：整數西元年。
- `sources`：本年資料來源代碼陣列，依交叉驗證情況為 `["tpe","nwt"]` 或單一 `["tpe"]` / `["nwt"]`。
- `summary.total`：當年總天數（365 或閏年 366）。
- `summary.workdays` / `summary.holidays`：上班日 / 放假日數，兩者相加等於 total。
- `days[]`：依日期排序，**全年每一天**皆有一筆。
  - `date`：`YYYY-MM-DD`。
  - `weekday`：ISO 星期，整數 1–7（1=週一 … 7=週日）。
  - `isWorkday`：布林，一般機關學校當日是否上班（核心欄位）。
  - `name` / `category` / `description`：若該日為來源中的特殊日則填入，否則為空字串。

設計取捨：

- **刻意不放會變動的時間戳**（如 generatedAt），讓資料無變更時不產生雜訊 commit；產生時間由 git 歷史提供。
- 不另設 `isHoliday` 欄位，避免與 `isWorkday` 語意混淆（來源 isHoliday 對「特定節日」標 `是` 但機關照常上班）。原始判斷意圖以 `isWorkday` 為準，`category` 供追溯。

## 4. 資料模型：分類 → isWorkday 規則

`isWorkday` 推導步驟（單一來源 → 全年逐日）：

1. 基準：星期一～五為上班（True）、週六日為放假（False）。
2. 依該日在來源特殊日清單中的 `category` 套用覆蓋：

| holidayCategory | 對一般機關語意 | 對 isWorkday 的作用 |
|---|---|---|
| 星期六、星期日 | 放假 | 設為 False |
| 放假之紀念日及節日 | 放假 | 設為 False |
| 補假 | 放假 | 設為 False |
| 調整放假日 | 放假 | 設為 False |
| 補行上班 | 上班（補班）| 設為 True（覆蓋週末）|
| 特定節日（如警察節）| 一般機關照常 | **不覆蓋**（依基準），僅保留 name/description |
| 其他未知值 | 無法判斷 | **觸發 UnknownCategory → 開 issue 中斷** |

已知分類常數集中於 `model.py`，以集合定義 `NON_WORKING_CATEGORIES`、`WORKING_CATEGORIES`、`INFO_ONLY_CATEGORIES`（特定節日）。任何不在三集合內的分類即為未知。

警察節驗證：`tpe` 標「特定節日」→ 不覆蓋 → 6/15(週一) 上班；`nwt` 無此日 → 平日 → 上班。兩來源推導皆為「上班」，比對一致，不誤開 issue。

## 5. 模組切分

各模組單一職責、可獨立測試：

- `taiwan_work_calendar/errors.py`：自訂例外
  - `SchemaChangedError`、`UnknownCategoryError`、`SourceMismatchError`（皆攜帶足以寫入 issue 的細節）。
- `taiwan_work_calendar/sources.py`：來源存取
  - 下載 tpe / nwt CSV；解析為正規化記錄 `dict[date_str] -> {name, category, description}`；驗證 CSV 欄位名稱（不符 → `SchemaChangedError`）。下載函式與解析函式分離，解析可吃字串以利測試。
- `taiwan_work_calendar/model.py`：規則與建模
  - 分類常數集合；`derive_is_workday(date, special_record|None)`；`build_year_days(year, records)` 產生全年逐日；偵測未知分類（→ `UnknownCategoryError`）。
- `taiwan_work_calendar/reconcile.py`：交叉驗證
  - `reconcile_year(year, tpe_records, nwt_records)`：逐日比對兩來源推導後 isWorkday，回報差異清單；有差異 → `SourceMismatchError`。
- `taiwan_work_calendar/issues.py`：GitHub issue
  - 透過 GitHub REST API 建立 issue；**依標題簽章去重**（先查同標題的 open issue，存在則不重開）；無 `GITHUB_TOKEN` 時記 log 並略過建立（本機執行不阻斷）。
- `taiwan_work_calendar/builder.py`：單年組裝
  - 整合來源、套規則、組 summary，產出單年 dict。
- `taiwan_work_calendar/main.py`：流程編排 + CLI
  - 參數解析、決定目標年份、容錯下載、先全驗證再全寫檔、halt 控制、退出碼。

寫檔：`data/YYYY.json`，UTF-8、`ensure_ascii=False`、2 空白縮排、結尾換行，確保 diff 穩定。

## 6. 執行流程（先全驗證、再全寫檔）

```
1. 解析 CLI → 決定目標年份集合 target_years
     預設：[當前西元年 + 1]
     --year 2025 或 --year 2025,2026,2027 → 指定覆寫
2. 下載 tpe、nwt（各自 try）；任一失敗記 warning 續行
     兩者皆失敗 → 致命錯誤，exit 1（不開 issue）
3. 對「可用來源」解析並驗證欄位（SchemaChanged → 開 issue + exit）
4. 對每個 target_year：
     a. 找出含該年的來源
     b. 無任何來源含該年 → 記 log「尚未發布」，soft-skip 該年
     c. 僅一來源含該年 → 記錄 sources=[該來源]，驗證未知分類
     d. 兩來源皆含 → 驗證未知分類 + reconcile（mismatch → 開 issue + exit）
   （此階段只驗證、不寫檔；任一年觸發中斷則整批不寫）
5. 全部通過 → 逐年 build 並寫出 data/YYYY.json
6. 若所有 target_year 皆 soft-skip → exit 0（no-op）
```

中斷時：呼叫 `issues.py` 建立對應 issue（去重）後，以非零退出，且**未寫出任何檔案**。

## 7. 自動開 issue 內容

- 標題簽章（用於去重），例如：
  - 來源不一致：`[資料不一致] 2027 年 tpe/nwt 辦公日推導結果不符`
  - 欄位變動：`[格式變動] 來源 nwt CSV 欄位與預期不符`
  - 未知分類：`[未知分類] 來源 tpe 出現未定義分類「○○○」`
- 內文：問題摘要、差異明細（日期、各來源推導值/原始分類）、建議修正方向、觸發時間與 workflow run 連結（若於 Actions 環境）。
- 標籤：`data-issue`（workflow 需具 `issues: write`）。

## 8. GitHub Actions

檔案 `.github/workflows/update-calendar.yml`：

- 觸發：
  - `schedule: cron: "0 0 1,15 7-12 *"`（UTC 0 點＝臺灣 8 點；每年 7–12 月 1 日與 15 日）
  - `workflow_dispatch`（可手動，並可輸入 year 參數）
- 權限：`contents: write`（commit data/）、`issues: write`（開 issue）。
- 步驟：checkout → 安裝 uv → `uv run` 執行轉換腳本（預設處理來年）→ 若 `data/` 有 diff 則 commit & push（Conventional Commits，作者含 Claude 共同作者）。
- 腳本以非零退出時 job 失敗並已開好 issue；GitHub 原生會通知失敗（涵蓋「兩來源都下載失敗」情形）。

## 9. 測試（pytest）

不依賴網路，使用內建小型固定 CSV 樣本字串：

- 分類規則表逐項：四種放假類 → False；補行上班 → True（覆蓋週末）；特定節日 → 不覆蓋。
- `build_year_days`：全年天數正確（含閏年 366）、summary 加總正確、排序正確。
- 警察節情境：tpe 有「特定節日」、nwt 無 → reconcile 一致、不報錯。
- reconcile 偵測：人為造一筆推導不一致 → 拋 `SourceMismatchError` 且差異明細正確。
- 未知分類：注入未知 category → 拋 `UnknownCategoryError`。
- 欄位變動：改欄位名 → 拋 `SchemaChangedError`。
- issue 去重：同標題已存在時不重開（以可注入的假 API client 測試）。
- CLI 目標年份：預設來年；`--year` 覆寫；來年未發布 → soft-skip exit 0。

## 10. 專案結構

```
taiwan-work-calendar/
├── data/                      # 產出 YYYY.json
├── taiwan_work_calendar/      # Python 套件
│   ├── __init__.py
│   ├── errors.py
│   ├── sources.py
│   ├── model.py
│   ├── reconcile.py
│   ├── issues.py
│   ├── builder.py
│   └── main.py
├── tests/
│   └── test_*.py
├── docs/                      # 專案文件（spec 等）
├── .github/workflows/update-calendar.yml
├── pyproject.toml             # uv 管理
├── .gitignore                 # 含 work/ temp/ tmp/
└── README.md                  # 實作完成後補
```

## 11. 不做的事（YAGNI）

- 不處理人事行政總處原始文件/圖檔解析（直接用結構化 CSV）。
- 不建資料庫、不做 API 服務（純檔案產出）。
- 不在 JSON 內放變動時間戳。
- 不自動修正來源差異（交由開發者依 issue 處理）。
- 「資料不完整」與「單一來源下載失敗」不自動開 issue（依使用者選擇）。
