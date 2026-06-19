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
