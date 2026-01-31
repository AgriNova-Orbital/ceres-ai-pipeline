import numpy as np
import matplotlib.pyplot as plt

# 1. 小麥生長週期數據 (Zadoks Scale)
stages = ['Seedling', 'Tillering', 'Stem Elongation', 'Booting', 'Heading', 'Flowering', 'Grain Filling']
days_start = [0, 10, 30, 45, 60, 70, 105] 
days_duration = [10, 20, 15, 15, 10, 35, 20]  # 預估天數間隔 [1]

# 2. 小麥鏽病高斯函數參數
# Y(t) = a + b * exp(-(t-m)^2 / (2s^2))
t = np.linspace(0, 140, 500)  # 時間軸 (天)
a = 0      # 起始病情 (Baseline)
b = 85     # 峰值嚴重程度 (Peak Severity, %)
m = 80     # 高峰期出現時間 (Peak day, 假設在穀粒填充期)
s = 15     # 標準差 (流行期的寬度)

def gaussian_progress(t, a, b, m, s):
    return a + b * np.exp(-((t - m)**2) / (2 * s**2))

y_disease = gaussian_progress(t, a, b, m, s)

# --- 繪圖 ---
fig, ax1 = plt.subplots(figsize=(12, 7))

# 繪製生長週期 (甘特圖風格)
colors = plt.cm.YlGn(np.linspace(0.3, 0.9, len(stages)))
for i, stage in enumerate(stages):
    ax1.barh(0.5, days_duration[i], left=days_start[i], color=colors[i], 
             edgecolor='black', alpha=0.6, label=f'GS: {stage}')
    # 標註階段名稱
    ax1.text(days_start[i] + days_duration[i]/2, 0.5, stage, 
             ha='center', va='center', fontsize=9, rotation=45)

# 繪製鏽病高斯曲線
ax2 = ax1.twinx()
ax2.plot(t, y_disease, color='red', linewidth=3, label='Rust Progress (Gaussian)')
ax2.fill_between(t, 0, y_disease, color='red', alpha=0.1)

# 設定圖表標籤
ax1.set_xlabel('Days After Sowing (DAS)', fontsize=12)
ax1.set_yticks([])
ax1.set_xlim(0, 140)
ax1.set_title('Wheat Growth Cycle & Rust Epidemic Gaussian Model', fontsize=14, fontweight='bold')

ax2.set_ylabel('Disease Severity (%)', color='red', fontsize=12)
ax2.set_ylim(0, 100)

# 標註 R0 概念
ax2.annotate(r'Epidemic Threshold $R_0 > 1$', xy=(m-25, 20), xytext=(m-45, 40),
             arrowprops=dict(facecolor='black', shrink=0.05), fontsize=10)

plt.tight_layout()
plt.show()