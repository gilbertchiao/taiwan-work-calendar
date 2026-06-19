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
