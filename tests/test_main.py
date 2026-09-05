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
    # 提供一筆放假日即可，其餘平日由程式補
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
    tpe = _records_for_year(
        2027, {"20270925": {"name": "", "category": "補行上班", "description": ""}}
    )
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


def test_run_generates_with_override_resolving_mismatch(tmp_path):
    # 2027-09-25(週六) tpe 補行上班(上班)、nwt 無(放假) → 不一致；以覆寫信任 tpe 解決
    tpe = _records_for_year(
        2027, {"20270925": {"name": "", "category": "補行上班", "description": ""}}
    )
    nwt = _records_for_year(2027)
    code = main.run(
        ["--data-dir", str(tmp_path)],
        today=date(2026, 7, 1),
        fetchers={"tpe": lambda: tpe, "nwt": lambda: nwt},
        client=None,
        overrides={"2027-09-25": {"trust": "tpe"}},
    )
    assert code == 0
    data = json.loads((tmp_path / "2027.json").read_text(encoding="utf-8"))
    day = next(d for d in data["days"] if d["date"] == "2027-09-25")
    assert day["isWorkday"] is True
    assert day["category"] == "補行上班"


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
