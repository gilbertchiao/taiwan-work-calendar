from taiwan_work_calendar import issues
from taiwan_work_calendar.errors import UnknownCategoryError


class FakeClient:
    def __init__(self, existing=False):
        self.existing = existing
        self.created = []

    def find_open_issue(self, title):
        return self.existing

    def create_issue(self, title, body, labels):
        self.created.append((title, body, labels))


def test_report_error_creates_issue_when_absent():
    client = FakeClient(existing=False)
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=client)
    assert len(client.created) == 1
    assert client.created[0][0] == err.issue_title()
    assert "data-issue" in client.created[0][2]


def test_report_error_skips_duplicate():
    client = FakeClient(existing=True)
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=client)
    assert client.created == []


def test_report_error_without_client_does_not_raise():
    err = UnknownCategoryError("tpe", "颱風假", "20270815")
    issues.report_error(err, client=None)  # 不應拋例外
