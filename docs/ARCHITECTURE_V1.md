# Ceres AI Pipeline — 系統架構 V1

> 文件版本：v1.0 | 最後更新：2026-04-01

---

## 1. 系統目標

Ceres AI Pipeline 是一套以 Sentinel-2 衛星時序資料為基礎的小麥鏽病風險預測平台。核心能力：

1. **資料取得**：透過 Google Earth Engine (GEE) 與 Google Drive 下載 Sentinel-2 每週特徵 GeoTIFF
2. **資料處理**：合併多 tile、正規化、切 patch、建構 NPZ 訓練資料集
3. **模型訓練**：CNN-LSTM 模型，支援 staged training matrix（不同粒度 × 不同樣本數）
4. **評估選模**：自動 threshold tuning，recall-first 策略
5. **Web 介面**：操作者透過 WebUI 排程任務、監控進度、預覽資料
6. **使用者認證**：Google OAuth + 本地帳密雙軌登入

**服務對象**：農業分析團隊（內部使用者），非公開網站。

---

## 2. 模組邊界

```
┌─────────────────────────────────────────────────────────┐
│                      Next.js Frontend                   │
│  (frontend/)  Port 3000, SSR + Client Components        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (JSON API)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Flask API Layer                       │
│  (apps/)  Gunicorn on Port 5055                         │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │ api_auth │ api_admin│ api_runs │ api_oauth│          │
│  └──────────┴──────────┴──────────┴──────────┘          │
│  ┌──────────────────────────────────────────┐           │
│  │       wheat_risk_webui (主 app)           │           │
│  │  SQLite Store / Session / Job Enqueue     │           │
│  └──────────────────────────────────────────┘           │
└──────────────────────┬──────────────────────────────────┘
                       │ RQ Job Queue (Redis)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    RQ Worker                             │
│  (modules/jobs/worker.py + modules/jobs/tasks.py)       │
│  執行：download, export, training, evaluation 等長任務   │
│  ※ 唯一需要 GPU 的容器                                   │
└──────────────────────┬──────────────────────────────────┘
                       │ subprocess / function call
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Pipeline Scripts                        │
│  (scripts/)                                             │
│  download_drive_folder.py / build_npz_dataset_from_     │
│  geotiffs.py / run_staged_training_matrix.py /          │
│  eval_staged_training_matrix.py / export_weekly_*.py    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  持久化 & 狀態層                          │
│  ┌────────────────────┐  ┌────────────────────┐         │
│  │  SQLite (app.db)   │  │  Redis             │         │
│  │  - 使用者帳密/設定  │  │  - RQ Job Queue    │         │
│  │  - Job 歷史記錄     │  │  - Job Meta/進度   │         │
│  │  - 系統初始化狀態   │  │  - Session (可選)   │         │
│  └────────────────────┘  └────────────────────┘         │
│                                                         │
│  ┌────────────────────────────────────────────┐         │
│  │  檔案系統 (Volumes)                         │         │
│  │  data/    - raw GeoTIFF, NPZ, staged datasets│       │
│  │  runs/    - 訓練產出 checkpoints, summary   │         │
│  │  reports/ - inventory CSV, 評估報告          │         │
│  │  logs/    - 應用日誌                         │         │
│  │  state/   - app.db                          │         │
│  └────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### 2.1 WebUI（前端）

| 項目 | 說明 |
|------|------|
| 框架 | Next.js (App Router) + Tailwind CSS |
| 位置 | `frontend/` |
| 部署口 | Port 3000（容器內）→ 對外 3002 |
| 職責 | 頁面渲染、表單提交、Job 狀態輪詢、OAuth 登入流程 |
| 對後端通訊 | 純 JSON API，透過 `API_URL=http://web:5055` proxy |

### 2.2 API 層（後端）

| Blueprint | 路由前綴 | 職責 |
|-----------|----------|------|
| `api_auth` | `/api/auth/*` | 登入、登出、改密碼、session 管理 |
| `api_admin` | `/api/admin/*` | 初始化流程、系統設定（OAuth config、redirect URL） |
| `api_runs` | `/api/runs/*`, `/api/jobs/*` | Job 提交（enqueue）、Job 歷史查詢、Job 狀態輪詢 |
| `api_oauth` | `/api/oauth/*` | Google OAuth callback、Drive token 管理 |
| `wheat_risk_webui` | `/`, `/api/preview/*` | 主 app factory、資料預覽端點（raw/patch 圖片） |

**共用基礎設施**：
- `SQLiteStore`（`modules/persistence/sqlite_store.py`）：所有狀態讀寫
- RQ `Queue`：Job 入隊
- Flask `session`：登入態（cookie-based）

### 2.3 Worker

| 項目 | 說明 |
|------|------|
| 入口 | `modules/jobs/worker.py` |
| 任務定義 | `modules/jobs/tasks.py` |
| 佇列 | Redis RQ，queue name = `default` |
| 主要任務 | `run_script`（通用 shell 執行）、`download_drive_folder_task`、`export_weekly_risk_task` 等 |
| 進度回報 | RQ Job `meta` 欄位（step, progress），由前端輪詢 `/api/jobs/<id>` 讀取 |
| 資源需求 | GPU（CUDA）僅 worker 需要 |

### 2.4 狀態層

| 儲存 | 技術 | 內容 |
|------|------|------|
| 關聯資料 | SQLite (`state/app.db`) | 使用者、密碼 hash、系統設定、Job 歷史 |
| 任務佇列 | Redis | RQ queue + job meta |
| 檔案 | 掛載 Volume | GeoTIFF、NPZ、checkpoint、logs |

### 2.5 基礎設施

| 服務 | 容器 | 說明 |
|------|------|------|
| redis | `redis:7-alpine` | RQ 佇列，healthcheck: `redis-cli ping` |
| web | 本專案 Dockerfile | Gunicorn 2 workers，Flask app |
| worker | 本專案 Dockerfile | RQ worker，需 GPU |
| frontend | `frontend/Dockerfile` | Next.js standalone |

**部署工具**：Docker Compose，`Makefile` 簡化操作（`make up/down/reset/logs/test`）。

---

## 3. 資料流

### 3.1 主要 Pipeline 資料流

```
GEE / Google Drive
  │
  ▼
[download_drive_folder.py]
  │  下載每週 GeoTIFF → data/raw/france_2025_weekly/
  │  合併多 tile → 正規化檔名 fr_wheat_feat_YYYYWww.tif
  ▼
[build_npz_dataset_from_geotiffs.py]
  │  讀取 GeoTIFF stack → 切 patch → 插值缺漏週
  │  輸出 NPZ → data/wheat_risk/staged/L{1,2,4}/
  ▼
[run_staged_training_matrix.py]
  │  跑 nested loop：levels × steps
  │  輸出 checkpoint → runs/staged_final/L{level}/
  ▼
[eval_staged_training_matrix.py]
  │  掃 threshold → 選最佳 recall-first 配置
  │  輸出 summary.csv → runs/staged_final/summary.csv
  ▼
最佳模型 + threshold → 生產使用
```

### 3.2 WebUI 觸發流程

```
使用者點擊按鈕
  │
  ▼
前端 fetch POST /api/runs/enqueue
  │  body: { section, action, command }
  ▼
Flask 建立 RQ Job → Queue.enqueue()
  │  寫入 SQLite job_history
  ▼
Redis Queue
  │
  ▼
Worker 取得 Job → 執行 modules/jobs/tasks.py 中對應任務
  │  透過 job.meta 更新進度
  ▼
前端每 3 秒輪詢 GET /api/jobs/<id>
  │  讀取 status + meta.progress
  ▼
顯示即時進度
```

### 3.3 OAuth 登入流程

```
前端 → GET /api/oauth/login
  │  重導至 Google Consent Screen
  ▼
Google → callback /api/oauth/callback
  │  交換 token → 存入 SQLite
  ▼
前端取得 session → 後續請求帶 cookie
```

---

## 4. API 契約規範

### 4.1 通用約定

- **傳輸格式**：JSON（`Content-Type: application/json`）
- **認證方式**：Flask session cookie（登入後自動帶上）
- **日期格式**：ISO 8601（`2026-04-01T12:00:00+00:00`）
- **分頁**：暫無，Job 歷史回傳全量（後續可加 limit/offset）

### 4.2 錯誤回應格式

所有錯誤端點統一回傳：

```json
{
  "error": "人類可讀的錯誤訊息"
}
```

搭配適當 HTTP status code：
| Code | 用途 |
|------|------|
| 400 | 請求參數錯誤（缺欄位、格式不符） |
| 401 | 未認證（session 過期或未登入） |
| 403 | 無權限 |
| 404 | 資源不存在 |
| 500 | 伺服器內部錯誤 |

### 4.3 主要端點一覽

#### Auth

| 方法 | 路徑 | 說明 | Request Body |
|------|------|------|-------------|
| POST | `/api/auth/login` | 帳密登入 | `{ username, password }` |
| POST | `/api/auth/logout` | 登出 | — |
| GET | `/api/auth/me` | 取得目前使用者 | — |
| POST | `/api/auth/change-password` | 改密碼 | `{ new_password, confirm_password }` |

#### Jobs

| 方法 | 路徑 | 說明 | Request Body |
|------|------|------|-------------|
| POST | `/api/runs/enqueue` | 提交 Job | `{ section, action, command }` |
| GET | `/api/jobs` | Job 歷史列表 | — |
| GET | `/api/jobs/<id>` | 單一 Job 狀態 | — |

#### OAuth

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/oauth/login` | 開始 OAuth 流程 |
| GET | `/api/oauth/callback` | Google 回調 |
| POST | `/api/oauth/disconnect` | 中斷 OAuth |

#### Preview

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/preview/raw` | 預覽原始 GeoTIFF 圖片 |
| GET | `/api/preview/patch` | 預覽 patch 切割圖片 |

### 4.4 Job 狀態機

```
queued → started → finished
                 → failed
                 → canceled
```

Job meta 欄位：
- `step`：目前步驟描述（字串）
- `progress`：0-100 整數百分比

---

## 5. 錯誤模型

### 5.1 錯誤分層

| 層級 | 錯誤類型 | 處理方式 |
|------|---------|---------|
| 前端 | fetch 失敗、timeout | 顯示 toast，建議重試 |
| API | 參數驗證失敗 | 回傳 400 + error message |
| API | 認證失敗 | 回傳 401，前端導向登入頁 |
| Worker | script 執行失敗 | Job 狀態 → `failed`，result 含 stderr |
| Worker | 資源不足（OOM、GPU busy） | Job 失敗，需人工介入 |
| Pipeline | GEE quota 超限 | 指數退避重試，最終失敗拋出 |
| Pipeline | 檔案損毀/缺漏 | 記錄 warning，跳過該週，不阻斷整體流程 |

### 5.2 重試策略

- **RQ 層面**：不自動重試（避免浪費 GPU 資源），由操作者手動重新觸發
- **GEE API**：內建 exponential backoff（模組層級）
- **下載失敗**：單檔失敗不中斷整批，回傳 `failed_weeks` 計數

### 5.3 錯誤日誌

- Worker 日誌：`logs/` 目錄 + Docker stdout
- WebUI 日誌：`webui.log`
- 結構化欄位：timestamp、level、module、message

---

## 6. 可觀測性

### 6.1 現狀

| 機制 | 說明 |
|------|------|
| RQ Job meta | 前端輪詢 `/api/jobs/<id>` 取得即時進度 |
| Docker logs | `docker compose --profile <dev|beta|release> logs -f` 查看各服務日誌 |
| 檔案日誌 | `webui.log`, `worker.log`, `rq_worker.log` |

### 6.2 待增強（Backlog）

| 項目 | 優先度 |
|------|--------|
| 結構化 JSON logging（取代 print/散亂 log） | P1 |
| Prometheus metrics（queue length、job latency、GPU utilization） | P2 |
| 健康檢查端點 `/healthz` | P1 |
| 告警（Worker 離線、Queue 堆積超過閾值） | P2 |

---

## 7. 部署與回滾

### 7.1 部署流程

```bash
# 1. 確認 main 分支通過 CI
# 2. 建構映像（範例：release）
docker compose --profile release build

# 3. 滾動更新（零停機目標，目前為重啟式更新）
docker compose --profile release up -d --force-recreate

# 4. 驗證
curl http://localhost:5055/healthz   # 待實作
docker compose --profile release ps
docker compose --profile release logs --tail=50 web-release worker-release
```

### 7.2 回滾流程

```bash
# 1. 回退到上一個已知正常的 git tag/commit
git checkout <previous-tag>

# 2. 重建並重啟（範例：release）
docker compose --profile release build
docker compose --profile release up -d --force-recreate

# 3. SQLite 備份還原（若 schema 變更）
cp state/app.db state/app.db.backup
# 還原先前備份的 app.db
```

### 7.3 資料備份

| 資產 | 備份方式 | 頻率 |
|------|---------|------|
| SQLite `state/app.db` | cp 備份 + 定期外推 | 每次部署前 |
| 訓練 checkpoint `runs/` | 版本化 tar | 重大訓練後 |
| 原始資料 `data/` | Google Drive 鏡像 | 已有 |

### 7.4 環境變數

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `REDIS_URL` | 否 | `redis://localhost:6379/0` | Redis 連線 |
| `APP_DB_PATH` | 否 | `./state/app.db` | SQLite 路徑 |
| `WEBUI_SECRET_KEY` | 否 | `ceres-default-secret` | Flask session key |
| `USE_FAKEREDIS` | 否 | — | 設 `1` 啟用 FakeRedis（測試用） |

---

## 8. 風險與決策原則

### 8.1 已知風險

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| SQLite 單點寫入瓶頸 | 並發操作時可能 lock contention | 短期：WAL mode；長期：若使用者增長可遷 PostgreSQL |
| GEE API quota | 資料下載中斷 | 分批 export + dry-run 驗證 + exponential backoff |
| GPU 資源不足 | 訓練排隊時間長 | staged training 支援 CPU fallback（較慢但可用） |
| 無自動化測試覆蓋 E2E | 部署後才發現問題 | 已有 Selenium E2E 測試骨架，需持續補齊 |
| 前端輪詢開銷 | 多使用者同時操作時 API 負載 | 短期可接受；長期考慮 WebSocket/SSE |
| 資料檔案體積增長 | 磁碟空間耗盡 | 定期清理舊 runs + 壓縮歸檔 |

### 8.2 架構決策原則

1. **簡單優先**：能用 SQLite 就不用 PostgreSQL，能用 RQ 就不用 Celery。複雜度在真正需要時再引入。
2. **離線可操作**：所有 pipeline 步驟都提供 CLI 腳本，WebUI 是 convenience layer 不是硬依賴。
3. **GPU 資源集中**：只有 worker 容器需要 GPU，其餘服務無 GPU 依賴，降低部署成本。
4. **recall-first**：模型評估優先召回率（漏抓鏽病的代價高於誤報）。
5. **可重現**：訓練配置、threshold、dataset 版本都透過檔案記錄，確保可追溯。
6. **增量交付**：每週可交付一個可用版本，避免大爆炸式整合。

### 8.3 Tech Debt 記錄

| 項目 | 狀態 | 備註 |
|------|------|------|
| Flask session → JWT/Redis session | 待評估 | 目前 cookie session 可滿足需求 |
| 前端輪詢 → WebSocket | 後續考慮 | Job 進度即時推送 |
| 無 API 版本控制 | 可接受 | 內部系統，前端後端同步部署 |
| 單一 Redis 無 HA | 可接受 | 內部使用，Redis 掛了重啟即可 |

---

*文件結束*
