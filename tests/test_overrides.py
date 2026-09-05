import json

from taiwan_work_calendar import overrides


def test_load_overrides_missing_file_returns_empty(tmp_path):
    assert overrides.load_overrides(tmp_path / "nope.json") == {}


def test_load_overrides_reads_entries(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(
        json.dumps({"2026-05-01": {"trust": "tpe", "reason": "x"}}),
        encoding="utf-8",
    )
    ov = overrides.load_overrides(path)
    assert ov["2026-05-01"]["trust"] == "tpe"


def test_apply_overrides_forces_trusted_record():
    have = {
        "tpe": {
            "20260501": {"name": "勞動節", "category": "放假之紀念日及節日", "description": ""}
        },
        "nwt": {"20260501": {"name": "勞動節", "category": "特定節日", "description": ""}},
    }
    records = {"20260501": have["nwt"]["20260501"]}  # 原本誤採 nwt
    ov = {"2026-05-01": {"trust": "tpe"}}
    result = overrides.apply_overrides_to_records(records, have, ov)
    assert result["20260501"]["category"] == "放假之紀念日及節日"


def test_apply_overrides_pop_when_trusted_has_no_record():
    have = {
        "tpe": {},
        "nwt": {"20260501": {"name": "x", "category": "特定節日", "description": ""}},
    }
    records = {"20260501": have["nwt"]["20260501"]}
    ov = {"2026-05-01": {"trust": "tpe"}}
    result = overrides.apply_overrides_to_records(records, have, ov)
    assert "20260501" not in result


def test_apply_overrides_ignores_unknown_trust_source():
    have = {"tpe": {"20260501": {"name": "x", "category": "特定節日", "description": ""}}}
    records = dict(have["tpe"])
    ov = {"2026-05-01": {"trust": "nwt"}}  # nwt 不在 have
    result = overrides.apply_overrides_to_records(records, have, ov)
    assert result == records
