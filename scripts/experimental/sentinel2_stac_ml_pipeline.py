from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any, Sequence


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Experimental Sentinel-2 STAC pipeline quicklook",
    )
    p.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[116.3, 36.1, 116.5, 36.3],
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    p.add_argument(
        "--date-range",
        type=str,
        default="2025-01-01/2025-12-30",
    )
    p.add_argument("--max-cloud", type=float, default=50.0)
    p.add_argument("--resolution", type=int, default=60)
    p.add_argument("--no-show", action="store_true")
    return p.parse_args(argv)


def _calculate_redsi(data: Any) -> Any:
    import numpy as np

    term1 = (705 - 665) * (data.rededge3 - data.red)
    term2 = (783 - 665) * (data.rededge1 - data.red)
    return (term1 - term2) / (2.0 * data.red)


def _phenology_weight(das: Any) -> Any:
    import numpy as np

    out = np.ones_like(das, dtype=np.float32)
    out[das < 60] = 0.3
    out[das > 150] = 0.1
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import numpy as np
    import pandas as pd
    from matplotlib import pyplot as plt
    from matplotlib.animation import FuncAnimation
    from odc.stac import load  # type: ignore[import-not-found]
    from pystac_client import Client  # type: ignore[import-not-found]

    args = _parse_args(argv)

    print("Connecting to AWS Earth Search STAC API...")
    catalog = Client.open("https://earth-search.aws.element84.com/v1")

    bbox = args.bbox
    date_range = args.date_range
    print(f"Searching Sentinel-2 data: {date_range}...")
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": float(args.max_cloud)}},
    )

    items = list(search.items())
    print(f"Found {len(items)} scenes. Loading bands...")
    data = load(
        items,
        bands=[
            "red",
            "green",
            "blue",
            "nir",
            "rededge1",
            "rededge2",
            "rededge3",
            "swir16",
        ],
        bbox=bbox,
        resolution=int(args.resolution),
        groupby="solar_day",
        chunks={},
    )

    data = data.where(data != 0) * 0.0001
    data = data.compute()

    print("Interpolating daily timeline...")
    time_pd = pd.to_datetime(data.time.values)
    data = data.assign_coords(time=time_pd).sortby("time")

    start_date = datetime.fromisoformat(date_range.split("/")[0]).date()
    end_date = datetime.fromisoformat(date_range.split("/")[1]).date()
    full_time_index = pd.date_range(start=start_date, end=end_date, freq="D")

    original_daily_index = pd.date_range(
        start=data.time.values[0], end=data.time.values[-1], freq="D"
    )
    data_daily = data.interp(time=original_daily_index, method="linear")

    limit_len = min(len(full_time_index), len(data_daily.time))
    data_daily = data_daily.isel(time=slice(0, limit_len))
    data_daily = data_daily.assign_coords(time=full_time_index[:limit_len])
    dates = data_daily.time.values

    print("Computing REDSI and NDVI...")
    data_daily["redsi"] = _calculate_redsi(data_daily)
    data_daily["ndvi"] = (data_daily.nir - data_daily.red) / (
        data_daily.nir + data_daily.red
    )

    print("Simulating phenology weights and environment factors...")
    num_days = len(data_daily.time)
    days_array = np.arange(num_days)
    pheno_weights = _phenology_weight(days_array)

    seasonal_temp = 15 - 15 * np.cos(2 * np.pi * (days_array - 30) / 365) + 2
    random_temp = np.random.normal(0, 2, num_days)
    simulated_lst = seasonal_temp + random_temp

    seasonal_wetness = 6 + 4 * np.sin(2 * np.pi * days_array / 365)
    random_wetness = np.random.normal(0, 2, num_days)
    simulated_lwd = np.clip(seasonal_wetness + random_wetness, 0, 24)

    def refined_temp_risk(t):
        return np.where(
            (t >= 4) & (t <= 16),
            1.0,
            np.where(t > 25, 0.0, np.exp(-((t - 12) ** 2) / 50)),
        )

    risk_temp = refined_temp_risk(simulated_lst)
    risk_wetness = 1 / (1 + np.exp(-(simulated_lwd - 4)))

    severity = np.zeros(num_days)
    r0_series = np.zeros(num_days)
    infection_start = 60
    severity[infection_start] = 0.05
    for d in range(1, num_days):
        if d < infection_start:
            continue
        current_r0 = (risk_temp[d] * risk_wetness[d] * 3.5) * pheno_weights[d]
        r0_series[d] = current_r0
        if current_r0 > 1:
            growth_rate = 0.15 * (current_r0 - 1)
            new_severity = severity[d - 1] * np.exp(growth_rate)
        else:
            new_severity = severity[d - 1] * 0.95
        severity[d] = np.clip(new_severity, 0, 100)

    mean_redsi = data_daily["redsi"].mean(dim=["x", "y"]).values

    fig = plt.figure(figsize=(20, 10))
    gs = fig.add_gridspec(3, 3)
    ax_rgb = fig.add_subplot(gs[0:2, 0])
    ax_redsi = fig.add_subplot(gs[0:2, 1])
    ax_r0 = fig.add_subplot(gs[0, 2])
    ax_env = fig.add_subplot(gs[1, 2])
    ax_trend = fig.add_subplot(gs[2, :])

    plt.suptitle("Wheat Rust Epidemiological Model (RGB vs REDSI)", fontsize=20)

    def get_rgb(time_idx):
        d = data_daily.isel(time=time_idx)
        rgb = np.stack([d.red.values, d.green.values, d.blue.values], axis=-1)
        return np.clip(rgb / 0.3, 0, 1)

    im_rgb = ax_rgb.imshow(get_rgb(0), animated=True)
    ax_rgb.set_title("Sentinel-2 True Color (RGB)")
    ax_rgb.axis("off")

    current_map_data = data_daily["redsi"].isel(time=0).values
    vmin_redsi = np.percentile(data_daily["redsi"], 5)
    vmax_redsi = np.percentile(data_daily["redsi"], 95)
    im_redsi = ax_redsi.imshow(
        current_map_data,
        cmap="RdYlBu_r",
        vmin=vmin_redsi,
        vmax=vmax_redsi,
        animated=True,
    )
    ax_redsi.set_title("Disease Stress Map (REDSI)")
    ax_redsi.axis("off")
    plt.colorbar(im_redsi, ax=ax_redsi, fraction=0.046, pad=0.04)

    dates_plot = pd.to_datetime(dates)
    ax_r0.plot(dates_plot, r0_series, color="purple", linewidth=2, label="R0")
    ax_r0.axhline(y=1, color="red", linestyle="--", linewidth=2, label="Threshold")
    (marker_r0,) = ax_r0.plot([], [], "ko")
    ax_r0.legend(loc="upper left", fontsize=8)
    ax_r0.grid(True, alpha=0.3)
    ax_r0.set_ylim(0, 4)

    ax_env.fill_between(
        dates_plot, 0, risk_wetness, color="blue", alpha=0.3, label="Wetness"
    )
    ax_env.plot(dates_plot, risk_temp, color="orange", linewidth=2, label="Temp Factor")
    (marker_env,) = ax_env.plot([], [], "ko")
    ax_env.legend(loc="upper right", fontsize=8)
    ax_env.grid(True, alpha=0.3)

    ax_trend.plot(dates_plot, severity, color="darkred", linewidth=2, label="Severity")
    ax_trend2 = ax_trend.twinx()
    ax_trend2.plot(dates_plot, mean_redsi, color="green", linestyle=":", label="REDSI")
    vline_trend = ax_trend.axvline(x=dates_plot[0], color="black", linestyle="--")
    ax_trend.set_ylim(0, 100)
    ax_trend.set_ylabel("Severity (%)")
    ax_trend2.set_ylabel("REDSI")
    ax_trend.legend(loc="upper left")

    def update_all(frame):
        current_date = dates_plot[frame]
        im_rgb.set_data(get_rgb(frame))
        im_redsi.set_array(data_daily["redsi"].isel(time=frame).values)
        marker_r0.set_data([current_date], [r0_series[frame]])
        marker_env.set_data([current_date], [risk_temp[frame]])
        vline_trend.set_xdata([current_date])
        return im_rgb, im_redsi, marker_r0, marker_env, vline_trend

    print("Launching animation...")
    FuncAnimation(fig, update_all, frames=len(dates), interval=50, blit=False)
    plt.tight_layout()
    if not bool(args.no_show):
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
