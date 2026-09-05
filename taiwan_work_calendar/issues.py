"""透過 GitHub REST API 建立 issue，並以標題去重避免每月重複開啟。"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_LABEL = "data-issue"
_TIMEOUT = 30


class GitHubIssueClient:
    """最小化的 GitHub issue 用戶端（僅查詢 open issue 與建立 issue）。"""

    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo  # 形如 "owner/name"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "taiwan-work-calendar",
        }

    def find_open_issue(self, title: str) -> bool:
        """以 GitHub search API 判斷是否已有同標題的 open issue。"""
        query = f'repo:{self.repo} is:issue is:open in:title "{title}"'
        url = f"{_API}/search/issues?q={urllib.parse.quote(query)}"
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        for item in data.get("items", []):
            if item.get("title") == title:
                return True
        return False

    def create_issue(self, title: str, body: str, labels: list[str]) -> None:
        url = f"{_API}/repos/{self.repo}/issues"
        payload = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            response.read()


def client_from_env() -> GitHubIssueClient | None:
    """於 GitHub Actions 環境（有 GITHUB_TOKEN 與 GITHUB_REPOSITORY）時建立 client。"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if token and repo:
        return GitHubIssueClient(token, repo)
    return None


def report_error(error, *, client: GitHubIssueClient | None = None) -> None:
    """依例外開立 issue；無 client 僅記 log，已存在同標題則不重開。"""
    title = error.issue_title()
    body = error.issue_body()
    if client is None:
        logger.warning("未設定 GitHub client，略過開立 issue：%s", title)
        return
    if client.find_open_issue(title):
        logger.info("已存在相同 issue，略過建立：%s", title)
        return
    client.create_issue(title, body, [_LABEL])
    logger.info("已建立 issue：%s", title)
