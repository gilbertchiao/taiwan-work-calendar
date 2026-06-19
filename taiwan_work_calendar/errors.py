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
        lines.append(
            "\n確認哪個來源正確後，於 `overrides.json` 新增對應日期並指定信任來源，"
            "commit 後下次執行即自動解決此歧異，例如：\n"
        )
        example = self.diffs[0]["date"] if self.diffs else "YYYY-MM-DD"
        lines.append(
            "```json\n"
            "{\n"
            f'  "{example}": {{ "trust": "tpe", "reason": "說明哪個來源正確及原因" }}\n'
            "}\n"
            "```"
        )
        return "\n".join(lines)
