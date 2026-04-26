# SeaCurrent UX 翻修 — 接續清單

承接 commit `9def277`（branch `claude/optimize-user-experience-WqjiY`）。原規劃見 `/root/.claude/plans/memoized-petting-liskov.md`（local）。

---

## 已完成（Phase 1–4, 6–9）

新增檔案：
- `assets/tokens.css`、`assets/a11y.css`、`assets/theme.js`
- `assets/components.js`（`<sea-header>`、`<sea-footer>`、`<sea-toast>`、`<sea-skeleton>`、`<sea-onboarding>`、`<sea-glossary>`）
- `assets/glossary.json`

頁面修改：4 頁都接上 skip link、`<main>` landmark、tokens、a11y、`<sea-toast>`、theme.js；forecast/tide 換 `<sea-header>`；app.html 接上 toast / onboarding / 資料起始徽章；tide canvas 包 `<figure role="img">`；forecast 港口項目可鍵盤操作。

---

## 未完成

### Phase 5（最大、需獨立 PR）：app.html inline JS 拆模組

**為何延後**：app.html 第 613–1180 行有 ~570 行 inline JS，引用 globals (`map`, `seedMarker`, `currentSimType`, `setSimType`…) 並被 `onclick="setSimType(...)"` 等 inline handler 直接呼叫。直接動會 break；需要專注 review。

**做法（保守、兩階段）**：

1. **第一階段：原樣搬到外部檔（不破壞 globals）**
   - 新增 `assets/app/index.js`，把 app.html 第 614–1179 行整段貼進去（不要動內容）
   - 把 app.html 的 `<script>...570 行...</script>` 換成 `<script src="assets/app/index.js"></script>`（**不要** `type="module"`，否則 globals 失效）
   - 驗收：實際送一筆 Person Overboard 模擬，收到 email；Network 內 POST body 與翻修前一致；點地圖能標座標；時間軸 scrub 正常

2. **第二階段：拆成 ES modules（需要把 inline `onclick` 改成 `addEventListener`）**
   - 把 `onclick="setSimType('leeway')"` 等改成 `data-sim-type="leeway"` + 一段 delegated listener
   - 同樣處理 `onchange="selectIdxVectorLayer(this.value)"`、`selectIdxScalarOverlay(this.value)`、`setSimType('oceandrift'|'openoil')`
   - 然後可拆成：`form.js`（表單＋submit）/ `map.js`（Leaflet init / seed marker / cursor）/ `layers.js`（vector + scalar 切換）/ `timeline.js`（slider + play + frame fetch）/ `simulate.js`（POST flow）/ `index.js`（boot）
   - 用 `type="module"` 載入；模組間用 `CustomEvent('sc:simulate-submit')` 之類解耦
   - 風險控管：建 `assets/app/_smoke.html` 載入所有模組驗 export；同樣實寄一次 Email

關鍵不能破壞的契約：
- `VERCEL_API_URL = 'https://seacurrent.vercel.app/api/simulate'`
- POST body shape（`lon, lat, duration, email, model_type, ...modelParams`）
- 表單 `id="simulationForm"`、submit button `id="submitBtn"` 不能換名
- frame URL pattern `scheduled_results/frames/{type}/h{HHH}.json` + index.json

---

### Phase 7 補完：frame cache LRU
- app.html 與 forecast.html 都有 `idxFrameCache = {}` / 對等變數，無上限
- 改成 `Map<key, value>` 並 LRU cap 24 frame
- 預期得跟 Phase 5 一起做（因為要動 inline JS）

### Phase 8 補完：Leaflet tile 在淺色模式下難讀
- 目前 4 頁都用 `https://{s}.basemaps.cartocdn.com/dark_all/...`
- 解法：偵測 `data-theme="light"`，動態換成 `https://{s}.basemaps.cartocdn.com/light_all/...`
- 訂閱 `window.addEventListener('sc:theme-change', ...)` 即時換
- 影響檔：app.html、forecast.html、tide.html 各 1 行 tileLayer URL + 1 個 listener

### Phase 9 補完：axe-core 稽核
- 跑 `npx @axe-core/cli http://localhost:3000/{index,app,forecast,tide}.html`
- 把所有 critical / serious 修到 0
- VoiceOver 過 app.html 表單；NVDA 過 tide 圖表
- Lighthouse Mobile（Moto G4 節流）：目標 perf ≥ 90、a11y ≥ 95

### 其他小項
- index.html footer 還用 hand-rolled，可考慮也換成 `<sea-footer>`
- forecast.html 的 `loadingMsg` 文字可改成中文 / 雙語
- `<sea-onboarding>` 目前只在 app.html；可考慮在 forecast.html 首訪也加一個極短導覽

---

## 怎麼接上（next session）

1. `cd /home/user/seacurrent && git checkout claude/optimize-user-experience-WqjiY`
2. `git pull` 確認與 remote 同步
3. 看這個檔案 + `git --no-pager log -1 9def277` 了解現況
4. 從 Phase 5 第一階段（搬到外部檔）開始最低風險

## 驗證流程（每次改完）

- 行動裝置 DevTools：iPhone SE 375×667、iPad 768×1024
- 鍵盤：Tab 走完整頁、確認每個 focusable 有 ring、無 trap
- toast：DevTools 斷網試送出模擬 → 確認 toast 出現 retry
- theme：點 header 切換鈕 → reload 後狀態保留
- 模擬實寄：送一筆 Person Overboard → 收到 email
