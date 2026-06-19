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


def test_makeup_workday_with_day_suffix_overrides_weekend():
    # 舊資料用「補行上班日」（多一個日），語意同補行上班
    assert model.derive_is_workday(date(2013, 2, 23), "補行上班日") is True  # 週六補班


def test_sunday_variant_is_holiday():
    # 部分舊資料單獨用「星期日」分類
    assert model.derive_is_workday(date(2013, 2, 24), "星期日") is False  # 週日


def test_special_festival_does_not_override():
    # 特定節日（警察節）不覆蓋：週一仍上班
    assert model.derive_is_workday(date(2026, 6, 15), "特定節日") is True


def test_commemorative_day_does_not_override():
    # 紀念日及節日（如婦女節，無「放假之」前綴）一般機關照常上班，不覆蓋基準
    assert model.derive_is_workday(date(2013, 3, 8), "紀念日及節日") is True  # 週五照常上班
    assert model.derive_is_workday(date(2014, 3, 8), "紀念日及節日") is False  # 週六本就放假


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
