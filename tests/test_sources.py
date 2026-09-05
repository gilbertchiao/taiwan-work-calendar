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


# ---- download 重試 ----


def test_download_retries_then_succeeds(monkeypatch):
    """前兩次失敗、第三次成功：應回傳內容，且不 sleep 真實時間。"""
    calls = []
    sleeps = []

    def fake_open(url):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("connection reset")
        return "Date,name\n"

    monkeypatch.setattr(sources, "_open_url", fake_open)
    monkeypatch.setattr(sources.time, "sleep", sleeps.append)

    assert sources.download("http://x") == "Date,name\n"
    assert len(calls) == 3
    # 指數退避：第一次等 base，第二次等 base*2
    assert sleeps == [sources._RETRY_BASE_DELAY, sources._RETRY_BASE_DELAY * 2]


def test_download_gives_up_after_max_attempts(monkeypatch):
    calls = []

    def always_fail(url):
        calls.append(url)
        raise OSError("boom")

    monkeypatch.setattr(sources, "_open_url", always_fail)
    monkeypatch.setattr(sources.time, "sleep", lambda _: None)

    with pytest.raises(OSError, match="boom"):
        sources.download("http://x")
    assert len(calls) == sources._MAX_ATTEMPTS
