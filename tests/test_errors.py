from taiwan_work_calendar.errors import (
    SchemaChangedError,
    SourceMismatchError,
    UnknownCategoryError,
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
        {
            "date": "2027-09-28",
            "tpe": True,
            "nwt": False,
            "tpe_category": "特定節日",
            "nwt_category": "放假之紀念日及節日",
        }
    ]
    err = SourceMismatchError(2027, diffs)
    assert "資料不一致" in err.issue_title()
    assert "2027" in err.issue_title()
    assert "2027-09-28" in err.issue_body()
