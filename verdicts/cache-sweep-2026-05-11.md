# Cache Sweep — 2026-05-11

全 cyclical cache 一輪 (~68 tickers across 22 細分產業)，applying `verdict-cyclical-tw` skill.

## Verdict 分布

| Verdict | 數量 | 比例 |
|---|---|---|
| 買 | **0** | 0% |
| 觀望 | 15 | ~22% |
| 不買 | 32 | ~47% |
| 不適用 | 21 | ~31% |
| 空 | 0 | 0% |

**沒有任何「買」訊號** — 整個 cyclical 宇宙在 2026-05-11 都不符合 robertshih framework 的 inflection 進場條件。這與 robertshih 2021 下半年自述退場邏輯結構性一致。

## 觀望標的（15）— 接近正面但 framework 未放行

| Ticker | Name | 細分 | 主要支撐 | 主要阻力 |
|---|---|---|---|---|
| 1402 | 遠東新 | PTA | PTA 上行 + 配息合格 | floor 高估，6x rule 對低絕對 EPS 失靈 |
| 1409 | 新纖 | PTA | PTA 供需轉緊 | floor 對低 EPS 股失靈 |
| 1463 | 強盛新 | 染整 | 2024 EPS 高峰 | 2025 turn down |
| 2009 | 第一銅 | 銅 | LME 銅向上 + supply 早期 | 個股 EPS-銅彈性弱 |
| 1102 | 亞泥 | 水泥 | 殖利率 5.5% 防禦支撐 | indicator 持平偏下 |
| 2606 | 裕民 | 散裝 | BDI +45% YoY | 散裝 supply 大規模 |
| 2637 | 慧洋-KY | 散裝 | 營收 YoY +35% | supply 大規模 |
| 2617 | 台航 | 散油混合 | 業績 YoY +22% | payout 邊界 47% |
| 2027 | 大成鋼 | 不鏽鋼 | EPS YoY +88%, payout 合格 | gap 仍高估 |
| 2069 | 運錩 | 不鏽鋼 | 11 年連發股利 | 業績持平 |
| 2010 | 春源 | 鋼鐵 | 殖利率 7.97% | EPS 資料不足 (low conf) |
| 2031 | 新光鋼 | 鋼鐵 | payout 合格 | 2025 EPS YoY -41% |
| 2409 | 友達 | 面板 | LCD ASP Q1 反轉 + 中韓退出 | Stage 2 borderline |
| 5347 | 世界先進 | 8 吋 foundry | quality semi-secular, indicator 向上 | framework 6x 系統性偏低 |
| 6488 | 環球晶 | 12 吋 wafer | LTA moat + cycle trough 反轉 | framework 對 quality cyclical 偏低 |

## 4 個 sweep 子表

### Sweep 1: 運輸 + 鋼鐵 (17)
0 買, 7 觀望 (2606, 2637, 2617, 2027, 2069, 2010, 2031), 8 不買, 2 不適用 (2208, 2061)

關鍵: SCFI 1911 向下 + 貨櫃 orderbook 31.6% = 整段貨櫃 不買 high-conf；散裝指標向上但 2026 交付潮觸發 supply 大規模 → 觀望非買。

### Sweep 2: 記憶體 + 面板 + 載板 + 矽晶圓 (16)
0 買, 3 觀望 (2409, 5347, 6488), 10 不買, 3 不適用 (5269, 8086, 3105)

關鍵: ABF 載板群統一不買（Ibiden +$3.3B = supply 大規模）；quality semi-secular (5347/6488) 暴露 framework 對 LTA 寡占型 cyclical 系統性偏低。

### Sweep 3: 石化 + 太陽能 + 金屬 + 水泥 (15)
0 買, 2 觀望 (2009, 1102), 4 不買, 9 不適用 (3576, 1304, 1310, 8358, 6274, 1503, 1530, 1101, 1110 部分)

關鍵: 中國乙烯 supply 大規模（佔 2026 全球新增 56%）壓制全石化群；多檔 transformation 偏 secular 觸發不適用。

### Sweep 4: 紡織 + 自行車 + 工具機 + 其他 (16)
0 買, 3 觀望 (1409, 1402, 1463), 8 不買, 5 不適用 (1432, 3034, 3035, 2107, 1530 重複)

關鍵: PTA 產業是最有趣訊號（中國七年擴產期 2026 結束 + Hengli 制裁）但被 6x floor rule 對低 EPS 股的盲點擋住；自行車 destocking 第三年仍未到 inflection。

## Hand-test (sweep 前) 4 ticker

| Ticker | Verdict | Confidence | 說明 |
|---|---|---|---|
| 2330 | 不適用 | high | secular_grower, EPS amplitude 3.8x < 5x |
| 2408 | 不買 | medium | DRAM/HBM, supply 早期但已啟動 |
| 6443 | 不適用 | medium | 太陽能, payout gate fail |
| 2603 | 不買 | high | 貨櫃, 3 條件同時觸發 (signature trade) |

## Cache 更新建議（送回 SKILL.md）

### 分類錯誤待修
- **5269 祥碩** — 不是 DRAM，是 controller IC secular_grower。從 cyclical 移除，加入 secular blacklist
- **8086 宏捷科** — 不是 DRAM，是 GaAs 代工。與 3105 同類
- **3105 穩懋** — 不是矽晶圓，是 GaAs foundry
- **2061** — skill 表寫「國祥」實為「風青」電線業，且已虧損
- **1530 亞崴** — 從「鋁」改為「工具機」
- **1503 士電** — 重電/電網 secular_now，鋁業比重小

### Borderline 重分類
- **8358 金居 / 6274 台燿** — AI server CCL/銅箔升級為 borderline secular_grower
- **1101 台泥** — 儲能/海外多元化使其 defensive_now（cache 已有 (?) 標記，可確認）
- **6505 台塑化** — unclassifiable 標註可移除，純歸 cyclical
- **3034 聯詠** — 振幅 3.3x < 5x，確認為 secular，cache (?) 標記可解除

### Framework 結構性 mismatch（累積中，待 ≥3 案例提議 tuning）
1. **低絕對 EPS + 高 P/B 折價的化纖/紡織 cyclical**（1402, 1409）— 6x EPS floor 結構失靈，建議增列 P/B < 0.6 倍且 NAV ≥ 2× 現價作為替代 buy condition
2. **Quality semi-secular cyclical**（5347, 6488，LTA + 寡占 + 長期能見度）— 6x floor 系統性偏低，需要 secular 加權
3. **減資代配息**（3481 群創）— Stage 2 payout gate 機械式 fail 但公司可能健康，Edge cases 需特殊處理

## 整體結論

1. 2026 年中 cyclical 宇宙處於 robertshih framework 的「全面 stand down」狀態 — 大部分產業 supply response 已 大規模 啟動 (貨櫃、散裝、ABF、石化、HBM)；少數 indicator 向上（PTA、銅、LCD、quality semi）的個股都被 floor gap 或 framework 結構盲點擋住
2. Framework 在 2026-05 此一時點守紀律輸出 0 買，與 robertshih 自述「2021 下半年退場、後續以維持為主」邏輯結構性一致 — 這是框架的核心價值
3. 真正接近正面的少數標的（1402 遠東新、2027 大成鋼、2606 裕民、5347 世界先進）值得用其他 framework 補充判讀（如 P/B 折價、quality cyclical secular tilt）
4. Cache 維護是持續工作 — 本輪暴露 6+ 個分類錯誤 / borderline 重分類，已寫入 SKILL.md changelog

## 完整 dossier
`/home/pgi/youtube/verdicts/<ticker>-2026-05-11.md`，每檔一份。
