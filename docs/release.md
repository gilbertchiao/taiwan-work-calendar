# 發版流程（Release Guide）

本文件說明本專案的版本策略與發版步驟，供維護者日後一致地發布新版本。

## 版本策略：軟體與資料分軌

本 repo 同時「發布」兩種性質不同的東西，兩者用不同方式管理：

| 對象 | 內容 | 版本管理方式 |
|---|---|---|
| **軟體** | `twcal` 轉換器、判斷規則、`viewer.html` 檢視器 | [語意化版本 SemVer](https://semver.org/lang/zh-TW/) 的 git tag（`vX.Y.Z`），與 `pyproject.toml` 的 `version` 同步 |
| **資料** | 每年新增的 `data/YYYY.json` | 持續更新的資料流，由自動 workflow commit 進 `main`，**一般不打 tag** |

核心原則：**tag 對應「軟體」**。因為對使用者最具相容性意義的是 JSON 輸出格式，而那屬於軟體層次；資料只是內容刷新，不改變介面契約。

### 版號怎麼跳（SemVer）

以 JSON 輸出格式為主要相容性契約來判斷：

- **MAJOR（`v2.0.0`）**：破壞性變更。例如更動 `days[]` 欄位名稱、改變 `isWorkday` 語意、調整 `summary` 結構等，會讓既有使用者的程式失效。
- **MINOR（`v1.1.0`）**：向後相容的新增。例如 `viewer.html` 新功能、JSON 新增「選填」欄位、新增來源等。
- **PATCH（`v1.0.1`）**：向後相容的修錯。例如 viewer 顯示 bug、判斷規則的邊界修正（不改格式）。

> 純粹新增某一年的 `YYYY.json` 不算軟體變更，不需要因此跳版號。

### 資料更新為什麼不打 tag

每年的 `data/YYYY.json` 由 GitHub Actions 自動產出並 commit。使用者要哪一年的資料，直接抓 `data/YYYY.json`（raw URL）或釘在某個 commit SHA 即可，檔案本身就是可定址的單位，毋須額外 tag。

若日後確有「不可變年度資料快照」的釘選需求，請使用**與軟體版本分開的 namespace**（例如 `data/2027`），切勿混入 `vX.Y.Z` 那一軌，以免語意混淆。

## 發版步驟

以下以發布 `vX.Y.Z` 為例（實際發 `v1.0.0` 時即依此流程）。

### 1. 確認 main 乾淨且與遠端同步

```bash
git checkout main
git pull --ff-only
git status   # 應無未提交變更
```

### 2. 對齊 `pyproject.toml` 版本

將 `pyproject.toml` 的 `version` 改為欲發布的版本（例如 `1.0.0`），透過分支與 PR 合併進 `main`：

```bash
git checkout -b chore/bump-X.Y.Z
# 編輯 pyproject.toml：version = "X.Y.Z"
git add pyproject.toml
git commit -m "chore: 版本升至 X.Y.Z"
git push -u origin chore/bump-X.Y.Z
gh pr create --base main --title "chore: 版本升至 X.Y.Z" --body "對齊 vX.Y.Z tag。"
gh pr merge chore/bump-X.Y.Z --squash
git checkout main && git pull --ff-only
git branch -d chore/bump-X.Y.Z
git push origin --delete chore/bump-X.Y.Z   # 清掉遠端已合併分支
```

> 為何要先合併再打 tag：tag 要指向「版本已對齊」的 main commit，確保 `pyproject.toml` 與 git tag 一致。

### 3. 打 annotated tag 並推送

使用 annotated tag（`-a`），它含作者、日期與訊息，優於 lightweight tag：

```bash
git tag -a vX.Y.Z -m "vX.Y.Z：一句話摘要

- 變更重點 1
- 變更重點 2"
git push origin vX.Y.Z
```

驗證 tag 指向 main HEAD：

```bash
git rev-parse vX.Y.Z^{commit}   # 應等於
git rev-parse origin/main
```

### 4. 開 GitHub Release

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes "變更說明…"
```

Release notes 建議涵蓋：主要變更、資料涵蓋年份、以及**相容性說明**（這版確立或變更了哪些 JSON 格式契約）。

驗證：

```bash
gh release view vX.Y.Z --json tagName,isDraft,isPrerelease,targetCommitish,url
```

## 發版後檢查清單

- [ ] `pyproject.toml` 的 `version` 與 git tag 一致。
- [ ] tag 為 annotated 且指向正確的 main commit。
- [ ] GitHub Release 已建立，且非草稿（draft）、非預發布（prerelease）。
- [ ] Release notes 含相容性說明。
- [ ] 本地與遠端無殘留的已合併分支。
