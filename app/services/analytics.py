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