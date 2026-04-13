# Ceres AI Pipeline — Sprint Plan W1-W2

> Sprint 週期：2026-04-01 ~ 2026-04-14（兩週）
> 目標：完成 MVP 整合測試、修補已知缺口、達到可 Demo 狀態

---

## Week 1 目標：穩固基礎、修補缺口

> 關鍵詞：能跑、能測、能部署

---

### W1 任務分解

| # | 任務 | Owner | Priority | DoD（驗收條件） |
|---|------|-------|----------|-----------------|
| W1-1 | **建立 `/healthz` 健康檢查端點** | 我 | P0 | `GET /healthz` 回傳 200 + `{"status":"ok","redis":true,"db":true}`，含 Redis/SQLite 連線檢查；加對應單元測試 |
| W1-2 | **Next.js 前端 → API proxy 串接驗證** | 隊友A | P0 | 前端 `frontend/` 透過 `API_URL` proxy 成功完成：登入 → 看到 Job Panel → 提交一個 test job → 看到進度更新 |
| W1-3 | **Worker 任務失敗處理與前端顯示** | 隊友B | P0 | 當 Worker script 執行失敗時：(1) Job 狀態正確設為 `failed` (2) stderr 寫入 job meta (3) 前端 JobPanel 顯示紅色失敗狀態 + 錯誤訊息前 200 字 |
| W1-4 | **Docker Compose 端到端啟動測試** | 我 | P0 | `docker compose --profile dev up --build` 後：(1) 四個容器全部 healthy (2) 前端 http://localhost:3002 可訪問 (3) 提交一個 download job 到完成全流程無錯誤 |
| W1-5 | **補齊 `api_runs.py` 缺少的 auth 檢查** | 我 | P1 | 所有 `/api/runs/*` 和 `/api/jobs/*` 端點在未登入時回傳 401，加測試覆蓋 |
| W1-6 | **前端 LoginForm / Register 頁面串接真實 API** | 隊友A | P1 | 目前前端表單提交到 `/api/auth/login` 和 `/api/register`，成功後跳轉 Dashboard，失敗顯示錯誤 |
| W1-7 | **Data Preview 頁面接上 `/api/preview/raw`** | 隊友B | P1 | 前端 data 頁面可選擇日期 → fetch 預覽圖 → 正確顯示，缺資料時顯示「無可用預覽」而非空白 |
| W1-8 | **整理 `.env.example` 與 README 環境變數說明** | 我 | P2 | `.env.example` 包含所有必要變數 + 註解；README Quick Start 步驟可一鍵照做不卡關 |

---

## Week 2 目標：功能完善、Demo Ready

> 關鍵詞：好用、好看、可展示

---

### W2 任務分解

| # | 任務 | Owner | Priority | DoD（驗收條件） |
|---|------|-------|----------|-----------------|
| W2-1 | **Admin Dashboard：顯示系統狀態** | 我 | P0 | Dashboard 頁面即時顯示：(1) Redis 連線狀態 (2) 佇列中 job 數量 (3) 最近 5 筆 job 狀態 (4) 磁碟使用量（data/runs 目錄） |
| W2-2 | **Job 完整生命週期：提交 → 進度 → 結果 → 重新執行** | 隊友A | P0 | 使用者可：(1) 從 UI 提交任意 pipeline 任務 (2) 看到即時進度條 (3) 完成後看到結果摘要 (4) 一鍵重新執行同一任務 |
| W2-3 | **Pipeline 全流程 Demo 劇本** | 隊友B | P0 | 準備一份可執行的 Demo 劇本：下載 → 建資料集 → 訓練 → 評估，每步驟從 WebUI 操作，全程 < 15 分鐘（可用小資料集） |
| W2-4 | **前端 Loading / Error / Empty 狀態統一處理** | 隊友A | P1 | 所有 fetch 請求統一：Loading 顯示 spinner、Error 顯示 toast + retry 按鈕、Empty 顯示引導文字；建立共用 `useApi` hook |
| W2-5 | **OAuth 流程前端整合測試** | 我 | P1 | 從前端「Sign in with Google」按鈕 → Google 同意頁面 → 回調 → 自動登入，全程無手動操作；加 E2E test（Selenium） |
| W2-6 | **Structured Logging 第一步** | 我 | P1 | Worker 與 WebUI 的 print/散亂 log 改為 Python `logging` 模組，輸出 JSON 格式到 stdout；保留檔案日誌到 `logs/` |
| W2-7 | **前端響應式佈局基本適配** | 隊友B | P2 | 在 1280px 和 768px 兩個斷點下，主要頁面（Login、Dashboard、Data）不破版、可操作 |
| W2-8 | **撰寫 `docs/ARCHITECTURE_V1.md` 對應的 runbook** | 隊友B | P2 | 文件包含：常見故障排查（Redis 掛了怎麼辦、Worker OOM 怎麼辦、SQLite locked 怎麼辦）對應操作步驟 |

---

## Owner 定義

| 代號 | 角色 | 職責範圍 |
|------|------|---------|
| **我** | 後端 / DevOps | API、Worker、基礎設施、部署、日誌 |
| **隊友A** | 前端 | Next.js 頁面、API 串接、UI 狀態處理 |
| **隊友B** | 全端 / ML | 前端頁面、Pipeline 腳本、Demo 劇本、文件 |

---

## Priority 定義

| 等級 | 含義 | 不做的後果 |
|------|------|-----------|
| **P0** | 必須本 sprint 完成 | 系統無法 Demo 或無法部署 |
| **P1** | 強烈建議完成 | 體驗差或技術債積累 |
| **P2** | 有空再做 | 錦上添花 |

---

## 每日 Standup 模板

```
日期：____-__-__
姓名：________

### 昨天完成
- 

### 今天預計
- 

### 阻礙 / 需要協助
- 

### 對照任務
- 正在做：W1-___ / W2-___
- 已完成：W1-___ / W2-___
```

### Standup 範例

```
日期：2026-04-02
姓名：我

### 昨天完成
- 完成 /healthz 端點實作與測試（W1-1）
- 修復 api_runs 缺少 auth 檢查的問題（W1-5 部分）

### 今天預計
- 完成 W1-5 剩餘端點的 auth 測試
- 開始 W1-4 Docker Compose E2E 驗證

### 阻礙 / 需要協助
- 無

### 對照任務
- 正在做：W1-4, W1-5
- 已完成：W1-1
```

---

## Sprint 進度追蹤表

### Week 1

| 任務 | Owner | 狀態 | 備註 |
|------|-------|------|------|
| W1-1 | 我 | ⬜ TODO | |
| W1-2 | 隊友A | ⬜ TODO | |
| W1-3 | 隊友B | ⬜ TODO | |
| W1-4 | 我 | ⬜ TODO | |
| W1-5 | 我 | ⬜ TODO | |
| W1-6 | 隊友A | ⬜ TODO | |
| W1-7 | 隊友B | ⬜ TODO | |
| W1-8 | 我 | ⬜ TODO | |

### Week 2

| 任務 | Owner | 狀態 | 備註 |
|------|-------|------|------|
| W2-1 | 我 | ⬜ TODO | |
| W2-2 | 隊友A | ⬜ TODO | |
| W2-3 | 隊友B | ⬜ TODO | |
| W2-4 | 隊友A | ⬜ TODO | |
| W2-5 | 我 | ⬜ TODO | |
| W2-6 | 我 | ⬜ TODO | |
| W2-7 | 隊友B | ⬜ TODO | |
| W2-8 | 隊友B | ⬜ TODO | |

狀態圖例：⬜ TODO | 🔵 IN PROGRESS | ✅ DONE | 🔴 BLOCKED

---

## Sprint 成功標準

兩週結束時需達成：

1. ✅ `docker compose --profile dev up --build` 一鍵啟動，四個服務正常運作
2. ✅ 從前端登入 → 提交任務 → 看到進度 → 看到結果，全流程暢通
3. ✅ 任務失敗時有清楚的錯誤訊息呈現
4. ✅ 可對外 Demo 一次完整的 pipeline 操作（< 15 分鐘）
5. ✅ 所有 P0 任務完成，P1 完成 ≥ 80%

---

*文件結束*
