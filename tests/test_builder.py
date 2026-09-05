from taiwan_work_calendar import builder


def test_build_year_structure_and_summary():
    records = {
        "20270101": {
            "name": "中華民國開國紀念日",
            "category": "放假之紀念日及節日",
            "description": "放假一日。",
        },
    }
    result = builder.build_year(2027, records, ["tpe", "nwt"])
    assert result["year"] == 2027
    assert result["sources"] == ["tpe", "nwt"]
    assert result["summary"]["total"] == 365
    assert (
        result["summary"]["workdays"] + result["summary"]["holidays"] == result["summary"]["total"]
    )
    assert len(result["days"]) == 365
    assert result["days"][0]["isWorkday"] is False


def test_merge_records_prefers_tpe_and_includes_tpe_only():
    tpe = {"20260615": {"name": "警察節", "category": "特定節日", "description": "a"}}
    nwt = {"20260619": {"name": "端午節", "category": "放假之紀念日及節日", "description": "b"}}
    merged = builder.merge_records(tpe, nwt)
    assert set(merged) == {"20260615", "20260619"}
    assert merged["20260615"]["name"] == "警察節"
