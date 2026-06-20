# 日曆檢視小工具 viewer.html

`data/viewer.html` 是一支純前端、零依賴的檢視工具，把 `data/YYYY.json` 以「政府行政機關辦公日曆表」的版面呈現：每月一格、一列三格、共四列十二個月，上班日白底、放假日淡粉紅底，方便快速目視某一年的上班／放假分布。

## 設計目標

這支工具刻意做成**單一 HTML 檔、無任何第三方套件**，原因有二：

第一，**避免供應鏈攻擊（Supply Chain Attack）**。完全不引入 CDN、npm 套件或任何外部 `<script src>`，所有程式碼都在同一個檔案內，並透過 `Content-Security-Policy` 限定只能載入同源資源，將可被竄改的面降到最低。

第二，**避免 query injection 與 XSS**。詳見下方「資安設計」。

## 使用方式

工具與 `YYYY.json` 放在同一目錄（`data/`），以 query parameter 指定要檢視的年度檔案：

```
viewer.html?file=2027.json
```

因為工具以 `fetch()` 載入 JSON，瀏覽器的同源政策（Same-Origin Policy）會封鎖 `file://` 協定，因此**必須透過 http(s) 開啟，不能直接用瀏覽器開啟本機檔案**。

### 本機快速預覽

```bash
cd data
python3 -m http.server 8000
# 瀏覽器開啟 http://127.0.0.1:8000/viewer.html?file=2026.json
```

### 部署到靜態網站

將 `data/` 目錄（含 `viewer.html` 與各 `YYYY.json`）部署到任何靜態主機（GitHub Pages、Amazon S3、Nginx 等），即可直接存取：

```
https://你的網域/路徑/viewer.html?file=2027.json
```

### 未指定檔名時

未帶 `file` 參數時，工具會顯示一個年份輸入框讓使用者輸入年份後跳轉。由於是純前端、無法列出目錄內容，工具不會自動偵測有哪些 `YYYY.json` 存在。

## 顯示內容

工具讀取 JSON 後呈現下列資訊：

- **標題**：自動將西元年換算為民國年，格式為「中華民國NNN年（西元YYYY年）政府行政機關辦公日曆表」。
- **摘要**：取自 `summary` 欄位的全年天數、上班日數、放假日數。
- **十二格月曆**：週日起始（日一二三四五六），日期格依 `isWorkday` 決定底色 —— `true` 為白底（上班日）、`false` 為淡粉紅底（放假日）。
- **圖例**：底部標示「上班日／放假日」的底色對照。

放假／上班的判斷**直接採用 JSON 的 `isWorkday` 欄位**，不在前端自行重算，因此補班日、補假、`overrides.json` 覆寫的結果都會正確反映。

每個日期格的星期欄位由資料的 `weekday`（ISO，週日=7）換算為「週日起始」的欄位位置。

### 不顯示的內容

參考的官方圖檔在每個日期下方會印農曆日期、節氣或節日名稱；本工具**刻意不顯示這些小字**以維持版面簡潔。放假日的節日名稱改放進該格的 `title` 屬性（tooltip），滑鼠移上去才會出現，不佔用版面空間。

## 資安設計

工具針對你最在意的兩類風險做了對應防護：

| 風險 | 防護措施 |
|---|---|
| 供應鏈攻擊 | 零第三方套件、無外部 `<script src>`；`Content-Security-Policy` 設為 `default-src 'self'`，即使日後檔案被竄改也僅能載入同源資源。 |
| 路徑穿越 / query injection | `file` 參數須通過嚴格白名單 `^[0-9]{4}\.json$`（四位數字 + `.json`），任何 `../`、絕對路徑或夾帶 `< > " ' ? #` 的檔名一律拒絕載入並顯示錯誤。 |
| DOM-based XSS | 所有畫面一律以 `document.createElement` + `textContent` 產生，**完全不使用 `innerHTML` 拼接外部資料**，從根本杜絕注入。年份輸入器送出前再以 `encodeURIComponent` 雙重保險。 |

> 白名單驗證屬於前端的第一道防線（提升使用體驗、避免發出明顯惡意的請求）。實際的檔案存取安全仍以主機端的靜態檔案服務設定為準 —— 正常的靜態主機本就不會將 `../` 解析到網站根目錄之外。

## 客製調整

| 需求 | 修改位置 |
|---|---|
| 改為「週一起始」 | 調整 `WEEK_HEADERS` 陣列順序，並修改 `isoToColumn()` 的對應邏輯。 |
| 調整放假日底色 | 修改 CSS 變數 `--holiday-bg` 與 `--holiday-border`。 |
| 顯示節日名稱小字 | 在 `buildMonthTable()` 的日期格內，額外加入一個以 `textContent` 設定 `day.name` 的子元素。 |
| 月份名稱改用阿拉伯數字 | 調整 `MONTH_NAMES` 陣列內容。 |
