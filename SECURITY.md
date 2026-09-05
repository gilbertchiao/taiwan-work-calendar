# 安全政策（Security Policy）

## 回報漏洞

本專案是純資料轉換工具，攻擊面很小，但仍歡迎回報任何安全問題，例如：

- `data/viewer.html` 的 XSS、路徑穿越或其他前端漏洞
- GitHub Actions workflow 的權限或注入問題
- 轉換程式在解析來源資料時可能被惡意內容觸發的問題

請透過 GitHub 的 **Private vulnerability reporting** 回報（repo 頁面 → Security → Report a vulnerability），**不要**直接開公開 issue，以免漏洞細節在修補前公開。

回報時請盡量附上：受影響的檔案或版本、重現步驟、影響範圍評估。

## 回應時程

這是個人維護的開源專案，沒有正式的 SLA。一般情況下會在 **14 天內**回覆並確認問題，並視嚴重程度盡快修補與發布新版本。

## 支援版本

僅最新的 release（`main` 分支對應的 tag）會收到安全修補。
