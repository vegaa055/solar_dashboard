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