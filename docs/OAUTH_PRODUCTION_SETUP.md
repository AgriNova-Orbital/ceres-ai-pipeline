# OAuth Production Setup

本文件說明 `Ceres AI / 穀神星AI` 在正式環境啟用 Google OAuth 的最小設定流程。後端目前 callback 路由為 `/api/oauth/callback`（實作位置：`apps/api_oauth.py`）。

## 1) Google Cloud Console 設定

- 建立 OAuth 2.0 Client ID（類型：Web application）
- Authorized domains 設為 `huskcat.com`
- Authorized redirect URIs 設定為：
  - `https://ceres.huskcat.com/api/oauth/callback`
  - `https://ceres-api.huskcat.com/api/oauth/callback`
- 下載 `client_secret.json`

## 2) 服務端設定（對應現行程式）

- 上傳 `client_secret.json` 至系統 Settings（`/api/oauth/upload-secret`）
- 設定 `redirect_base_url` 為正式網域（例如 `https://ceres.huskcat.com`）
- 後端登入入口為 `/api/oauth/login`，會以 `redirect_base_url + /api/oauth/callback` 組合 callback URL

## 3) 驗證流程

- 開啟應用並觸發 Google OAuth 連線
- 確認 Google 同意後會回到 `/api/oauth/callback`
- 確認最終導向 `/drive?connected=1`
- 檢查 OAuth token 已寫入 SQLite（供後續 Google Drive API 使用）

## 4) 上線注意事項

- 品牌名稱統一使用：`Ceres AI / 穀神星AI`
- 聯絡信箱：`a0903932792@gmail.com`
- `https://ceres.huskcat.com/privacy` 與 `https://ceres.huskcat.com/terms` 必須可公開存取
