import numpy as np
import xarray as xr
from pystac_client import Client
from odc.stac import load
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
from scipy.interpolate import interp1d

# -----------------------------------------------------------------------------
# 1. 初始化 STAC 客戶端
# -----------------------------------------------------------------------------
print("正在連接 AWS Earth Search STAC API...")
catalog = Client.open("https://earth-search.aws.element84.com/v1")

# 2. 定義觀測範圍與時間
bbox = [116.3, 36.1, 116.5, 36.3] # 範例小麥產區
date_range = "2025-01-01/2025-12-30" # 使用 2024 年因為 2025 年未來的數據可能不存在 (假設目前是2024/25年)
# 若您堅持要模擬未來，我們可以使用 2024 的數據但標示為 2025，或者如果 Sentinel-2 有預測/即時數據
# 為了確保程式能跑出結果，我們這裡使用 "2024-01-01/2024-12-30" 抓取完整的歷年生長季數據來演示
# (註：Sentinel-2 無法抓取「未來」的 2025 年底影像，除非是預測模型。這裡我們抓取最近一年的完整數據做演示)
date_range = "2025-01-01/2025-12-30" 

# 3. 搜尋 Sentinel-2 資料
# 關鍵波段：
# - B04 (Red), B08 (NIR) -> NDVI
# - B05, B06, B07 (Red Edge) -> NDRE, ARI (早期病害偵測)
# - B11 (SWIR) -> NDMI (水分)
print(f"搜尋 Sentinel-2 資料: {date_range}...")
search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=bbox,
    datetime=date_range,
    query={"eo:cloud_cover": {"lt": 50}}, # 放寬雲量限制以獲取更多數據 (後續插補會修正)
)

items = list(search.items())
print(f"找到 {len(items)} 個場景。正在加載波段數據...")

# 4. 加載波段數據
data = load(
    items,
    bands=["red", "green", "blue", "nir", "rededge1", "rededge2", "rededge3", "swir16"],
    bbox=bbox,
    resolution=60,       # 降低解析度以加速測試 (正式可改回 10或20)
    groupby="solar_day", 
    chunks={}            
)

# -----------------------------------------------------------------------------
# 5. 資料預處理與指數計算
# -----------------------------------------------------------------------------
# 數值標準化
data = data.where(data!= 0) * 0.0001
data = data.compute() # 下載數據

# 時間插補 (Interpolation) - 產生平滑的日數據
print("正在進行時間序列插補 (產生每日連續數據)...")
# Convert time to pandas datetime explicitly to avoid issues
time_pd = pd.to_datetime(data.time.values)
data = data.assign_coords(time=time_pd)
data = data.sortby('time')

# -----------------------------------------------------------------------------
# 5. 資料預處理與指數計算
# -----------------------------------------------------------------------------
# 數值標準化
data = data.where(data!= 0) * 0.0001
data = data.compute() # 下載數據

# 時間插補 (Interpolation) - 產生平滑的日數據
print("正在進行時間序列插補 (產生每日連續數據)...")
# Convert time to pandas datetime explicitly to avoid issues
time_pd = pd.to_datetime(data.time.values)
data = data.assign_coords(time=time_pd)
data = data.sortby('time')

# 建立每日時間軸 - 改為模擬 2025 年的時間軸顯示
start_date = pd.Timestamp("2025-01-01")
end_date = pd.Timestamp("2025-12-30")
full_time_index = pd.date_range(start=start_date, end=end_date, freq='D')

# 插補數據
original_daily_index = pd.date_range(start=data.time.values[0], end=data.time.values[-1], freq='D')
data_daily = data.interp(time=original_daily_index, method='linear')

limit_len = min(len(full_time_index), len(data_daily.time))
data_daily = data_daily.isel(time=slice(0, limit_len))
data_daily = data_daily.assign_coords(time=full_time_index[:limit_len])
dates = data_daily.time.values

# 計算植生指標 (Spectral Indices)
print("計算進階生理指標 (REDSI, NDVI)...")

# (1) REDSI (Red-Edge Disease Stress Index) - 條銹病黃金指標
# 公式: ((705 - 665) * (RE3 - Red) - (783 - 665) * (RE1 - Red)) / (2 * Red)
# Sentinel-2: Red=B4(665), RE1=B5(705), RE3=B7(783)
# REDSI 值越大，受銹病脅迫越嚴重 [1]
def calculate_redsi(data):
    term1 = (705 - 665) * (data.rededge3 - data.red)
    term2 = (783 - 665) * (data.rededge1 - data.red)
    return (term1 - term2) / (2.0 * data.red)

data_daily['redsi'] = calculate_redsi(data_daily)

# (2) NDVI (一般健康度) - 用於輔助參考
data_daily['ndvi'] = (data_daily.nir - data_daily.red) / (data_daily.nir + data_daily.red)

# -----------------------------------------------------------------------------
# 6. 環境數據模擬 & 流行病學動力學 (Epidemiology Dynamics)
# -----------------------------------------------------------------------------
print("模擬環境變數與生長階段 (Phenology)...")

num_days = len(data_daily.time)
days_array = np.arange(num_days)

# 1. 生長階段模擬 (Phenology - Zadoks Scale)
# 假設 DAS=0 在 1月1日
das_array = days_array # Days After Sowing (Simplified)

# 定義物候脆弱性權重 (Phenology Weight)
# GS30-85 (拔節至軟熟) 是關鍵監測期 [3]
def get_phenology_weight(das):
    # 假設拔節期約在 DAS 60 (3月初), 軟熟期在 DAS 150 (6月初)
    if 60 <= das <= 150: 
        return 1.0
    elif das < 60: # 苗期
        return 0.3
    else: # 成熟/收割
        return 0.1

pheno_weights = np.array([get_phenology_weight(d) for d in das_array])

# 2. 環境變數模擬
# 溫度: 模擬符合條銹病好發的春季氣溫
# 1月(2°C) -> 5月(16°C最佳) -> 7月(30°C過熱)
seasonal_temp = 15 - 15 * np.cos(2 * np.pi * (days_array - 30) / 365) + 2 
random_temp = np.random.normal(0, 2, num_days)
simulated_lst = seasonal_temp + random_temp

# 濕度/葉面濕潤 (LWD): 春季雨水多
seasonal_wetness = 6 + 4 * np.sin(2 * np.pi * days_array / 365) 
random_wetness = np.random.normal(0, 2, num_days)
simulated_lwd = np.clip(seasonal_wetness + random_wetness, 0, 24)

# -----------------------------------------------------------------------------
# 7. R0 傳播模型與風險演算 (R0 & Risk Algorithm)
# -----------------------------------------------------------------------------
print("計算 R0 與病情擴散模擬...")

# (A) 環境風險因子
# 溫度門檻: 4-16°C 最適 [4], >25°C 停止
def refined_temp_risk(t):
    return np.where((t >= 4) & (t <= 16), 1.0, 
           np.where(t > 25, 0.0, np.exp(-((t - 12)**2) / 50)))

risk_temp = refined_temp_risk(simulated_lst)

# 濕度門檻: >4hr 觸發 [5]
risk_wetness = 1 / (1 + np.exp(-(simulated_lwd - 4))) 

# (B) R0 與 病情模組 (SEIR 簡化版)
# 初始病情嚴重度 (Severity %)
severity = np.zeros(num_days)
r0_series = np.zeros(num_days)

# 假設在 DAS 60 (拔節期) 引入少量菌源
infection_start = 60
severity[infection_start] = 0.05 

for d in range(1, num_days):
    if d < infection_start:
        continue
        
    # 計算當日 R0: 環境適宜度 * 宿主脆弱性
    # 3.5 是假設的基礎傳播係數 (Basic Reproduction Number)
    current_r0 = (risk_temp[d] * risk_wetness[d] * 3.5) * pheno_weights[d]
    r0_series[d] = current_r0
    
    # 病情動態模擬 (Logistic Growth with R0 driver)
    if current_r0 > 1:
        # 當 R0 > 1, 病情指數增長
        growth_rate = 0.15 * (current_r0 - 1)
        new_severity = severity[d-1] * np.exp(growth_rate)
    else:
        # 當 R0 < 1, 病情受控或自然消退 (如高溫)
        new_severity = severity[d-1] * 0.95
    
    severity[d] = np.clip(new_severity, 0, 100)

# (C) 綜合風險地圖數據源
# 取 REDSI (真實遙感信號) 與 模擬 Severity (預測模型) 的混合
# 為了視覺化，我們將 REDSI 標準化並映射到風險
mean_redsi = data_daily['redsi'].mean(dim=['x', 'y']).values
# REDSI 越高 = 越嚴重 (High Risk)
norm_redsi = (mean_redsi - np.min(mean_redsi)) / (np.max(mean_redsi) - np.min(mean_redsi) + 1e-6)

# -----------------------------------------------------------------------------
# 8. 流行病學儀表板 (Epidemiological Dashboard)
# -----------------------------------------------------------------------------
fig = plt.figure(figsize=(20, 10))
gs = fig.add_gridspec(3, 3)

# 布局調整: 增加 RGB 顯示
# Col 0: RGB (True Color)
# Col 1: REDSI (Stress Map)
# Col 2: Charts
ax_rgb = fig.add_subplot(gs[0:2, 0])      # Map 1: RGB
ax_redsi = fig.add_subplot(gs[0:2, 1])    # Map 2: REDSI
ax_r0 = fig.add_subplot(gs[0, 2])         # Chart 1: R0 Dynamic
ax_env = fig.add_subplot(gs[1, 2])        # Chart 2: Env Trigger
ax_trend = fig.add_subplot(gs[2, :])      # Chart 3: Disease Severity & REDSI

plt.suptitle("Wheat Rust Epidemiological Model (RGB vs REDSI Analysis)", fontsize=22, fontweight='bold')

# --- 1. Map 1: RGB (True Color) ---
# 準備 RGB 數據 (亮度增強)
def get_rgb(time_idx):
    d = data_daily.isel(time=time_idx)
    # Stack bands to (Y, X, 3)
    rgb = np.stack([d.red.values, d.green.values, d.blue.values], axis=-1)
    # 影像增強: 原始反射率通常較低，除以 0.3 提亮，並限制在 0-1 之間
    return np.clip(rgb / 0.3, 0, 1)

im_rgb = ax_rgb.imshow(get_rgb(0), animated=True)
ax_rgb.set_title("Sentinel-2 True Color (RGB)", fontsize=16)
ax_rgb.axis('off')

# --- 2. Map 2: REDSI Stress Index ---
current_map_data = data_daily['redsi'].isel(time=0).values
vmin_redsi = np.percentile(data_daily['redsi'], 5)
vmax_redsi = np.percentile(data_daily['redsi'], 95)
im_redsi = ax_redsi.imshow(current_map_data, cmap='RdYlBu_r', vmin=vmin_redsi, vmax=vmax_redsi, animated=True)
ax_redsi.set_title("Disease Stress Map (REDSI)", fontsize=16)
ax_redsi.axis('off')

# Colorbar for REDSI
cbar = plt.colorbar(im_redsi, ax=ax_redsi, fraction=0.046, pad=0.04)
cbar.set_label("REDSI Value (Red=High Stress)", fontsize=12)

# --- 3. Charts Initialization ---
dates_plot = pd.to_datetime(dates)

# (A) R0 Dynamic Chart
ax_r0.plot(dates_plot, r0_series, color='purple', linewidth=2, label='Real-time R0')
ax_r0.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Outbreak Threshold')
ax_r0.fill_between(dates_plot, 0, r0_series, where=(r0_series>1), color='red', alpha=0.2)
marker_r0, = ax_r0.plot([], [], 'ko')

ax_r0.set_title("Epidemic R0 (Infection Rate)", fontsize=14)
ax_r0.legend(loc='upper left', fontsize=9)
ax_r0.grid(True, alpha=0.3)
ax_r0.set_ylim(0, 4)

# (B) Environmental Trigger (Temp + Wetness)
ax_env.fill_between(dates_plot, 0, risk_wetness, color='blue', alpha=0.3, label='Wetness')
ax_env.plot(dates_plot, risk_temp, color='orange', linewidth=2, label='Temp Factor')
marker_env, = ax_env.plot([], [], 'ko')

ax_env.set_title("Env Suitability (Temp & Wetness)", fontsize=14)
ax_env.legend(loc='upper right', fontsize=9)
ax_env.grid(True, alpha=0.3)

# (C) Severity Trend
ax_trend.plot(dates_plot, severity, color='darkred', linewidth=3, label='Estimated Severity (%)')
ax_trend2 = ax_trend.twinx()
ax_trend2.plot(dates_plot, mean_redsi, color='green', linestyle=':', label='Observed REDSI', alpha=0.7)
ax_trend2.set_ylabel("REDSI Index", color='green')

vline_trend = ax_trend.axvline(x=dates_plot[0], color='black', linestyle='--')

ax_trend.set_title("Disease Progression Forecast", fontsize=16)
ax_trend.set_ylabel("Severity (%)", color='darkred', fontsize=12)
ax_trend.set_ylim(0, 100)
lines_so, labels_so = ax_trend.get_legend_handles_labels()
lines_si, labels_si = ax_trend2.get_legend_handles_labels()
ax_trend.legend(lines_so + lines_si, labels_so + labels_si, loc='upper left')

# --- Animation Update ---
def update_all(frame):
    current_date = dates_plot[frame]
    
    # 1. Update Maps
    im_rgb.set_data(get_rgb(frame)) # Update RGB
    ax_rgb.set_title(f"True Color (RGB) - {current_date.strftime('%Y-%m-%d')}", fontsize=14)
    
    im_redsi.set_array(data_daily['redsi'].isel(time=frame).values) # Update REDSI
    ax_redsi.set_title(f"Disease Stress (REDSI) - {current_date.strftime('%Y-%m-%d')}", fontsize=14)
    
    # 2. Markers
    marker_r0.set_data([current_date], [r0_series[frame]])
    
    # 3. Bar/Lines
    vline_trend.set_xdata([current_date])
    
    # R0 Alert
    if r0_series[frame] > 1:
        ax_r0.set_title(f"R0 = {r0_series[frame]:.2f} (SPREADING!)", color='red', fontweight='bold')
    else:
        ax_r0.set_title(f"R0 = {r0_series[frame]:.2f} (Controlled)", color='black')

    return im_rgb, im_redsi, marker_r0, vline_trend

print("啟動流行病學動力學模擬儀表板 (RGB + REDSI)...")
ani = FuncAnimation(fig, update_all, frames=len(dates), interval=50, blit=False)
plt.tight_layout()
plt.show()