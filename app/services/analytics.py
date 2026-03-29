"""
app/services/analytics.py

Data processing layer — Pandas, NumPy, SciPy.
Sits between raw DB rows and the API routes.
"""
import numpy as np
import pandas as pd
from scipy.stats import linregress

from app.db import get_conn


def get_forecast_df(location_id: int, days: int = 7) -> pd.DataFrame:
    """Pull forecast rows for a location into a DataFrame."""
    sql = """
        SELECT forecast_time, temperature_2m, precipitation, cloud_cover,
               wind_speed_10m, shortwave_radiation, direct_radiation,
               diffuse_radiation, is_day
        FROM forecasts
        WHERE location_id = %s
          AND forecast_time >= NOW()
          AND forecast_time <= NOW() + INTERVAL %s DAY
        ORDER BY forecast_time
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=(location_id, days))
    df["forecast_time"] = pd.to_datetime(df["forecast_time"])
    return df


def get_actuals_df(location_id: int, days: int = 30) -> pd.DataFrame:
    """Pull historical actuals into a DataFrame."""
    sql = """
        SELECT observation_time, temperature_2m, precipitation, cloud_cover,
               wind_speed_10m, shortwave_radiation, direct_radiation,
               diffuse_radiation, is_day
        FROM actuals
        WHERE location_id = %s
          AND observation_time >= NOW() - INTERVAL %s DAY
        ORDER BY observation_time
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=(location_id, days))
    df["observation_time"] = pd.to_datetime(df["observation_time"])
    return df


def daily_summary(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """Aggregate hourly data to daily stats."""
    df = df.copy()
    df["date"] = df[time_col].dt.date
    summary = df.groupby("date").agg(
        peak_ghi=("shortwave_radiation", "max"),
        avg_ghi=("shortwave_radiation", "mean"),
        total_precip=("precipitation", "sum"),
        avg_temp=("temperature_2m", "mean"),
        avg_cloud=("cloud_cover", "mean"),
    ).reset_index()
    for col in ["peak_ghi", "avg_ghi", "total_precip", "avg_temp", "avg_cloud"]:
        summary[col] = summary[col].round(2)
    return summary


def rolling_irradiance(df: pd.DataFrame, time_col: str, window_hours: int = 6) -> pd.DataFrame:
    """Add a rolling mean of shortwave_radiation to smooth cloud transients."""
    df = df.copy().sort_values(time_col)
    df["ghi_rolling"] = (
        df["shortwave_radiation"]
        .rolling(window=window_hours, min_periods=1)
        .mean()
        .round(2)
    )
    return df


def irradiance_trend(df: pd.DataFrame, time_col: str):
    """Linear regression on daily peak GHI — returns slope, r², trend label."""
    summary = daily_summary(df, time_col)
    if len(summary) < 3:
        return None
    x = np.arange(len(summary))
    y = summary["peak_ghi"].values
    slope, intercept, r, p, se = linregress(x, y)
    trend = "stable" if abs(slope) < 5 else ("increasing" if slope > 0 else "decreasing")
    return {"slope_per_day": round(slope, 2), "r_squared": round(r ** 2, 3), "trend": trend}


def forecast_vs_actual(location_id: int) -> dict:
    """Compare last 7 days of forecasts vs actuals. Returns RMSE and MAE."""
    forecast_sql = """
        SELECT DATE(forecast_time) AS day, AVG(shortwave_radiation) AS fcst_ghi
        FROM forecasts
        WHERE location_id = %s AND forecast_time >= NOW() - INTERVAL 7 DAY
        GROUP BY day
    """
    actual_sql = """
        SELECT DATE(observation_time) AS day, AVG(shortwave_radiation) AS obs_ghi
        FROM actuals
        WHERE location_id = %s AND observation_time >= NOW() - INTERVAL 7 DAY
        GROUP BY day
    """
    with get_conn() as conn:
        f_df = pd.read_sql(forecast_sql, conn, params=(location_id,))
        a_df = pd.read_sql(actual_sql, conn, params=(location_id,))

    merged = pd.merge(f_df, a_df, on="day", how="inner")
    if merged.empty:
        return {"message": "Not enough overlapping data yet. Check back after a few days."}

    errors = merged["fcst_ghi"] - merged["obs_ghi"]
    return {
        "days_compared": len(merged),
        "rmse_wm2": float(np.sqrt((errors ** 2).mean()).round(2)),
        "mae_wm2": float(errors.abs().mean().round(2)),
        "daily": merged.assign(error=errors.round(2)).to_dict(orient="records"),
    }