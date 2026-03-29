"""
app/services/ingestion.py

Fetches forecast and historical data from Open-Meteo (free, no API key).
Upserts into forecasts / actuals tables and logs every run.

Open-Meteo docs: https://open-meteo.com/en/docs
"""
import requests
import logging
from datetime import datetime, timedelta, timezone

from app.db import get_conn

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "is_day",
]

def _build_params(lat: float, lon: float, fetch_type: str) -> dict:
    """Build query params for Open-Meteo API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "America/Phoenix",
        "wind_speed_unit": "kmh",
    }
    if fetch_type == "forecast":
        params["forecast_days"] = 7
    else:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=30)
        params["start_date"] = str(start)
        params["end_date"] = str(end)
    return params


def _upsert_rows(cursor, table: str, time_col: str, location_id: int, hourly: dict):
    """Insert or update rows. ON DUPLICATE KEY UPDATE makes this idempotent."""
    times = hourly["time"]

    sql = f"""
        INSERT INTO {table}
            (location_id, {time_col}, temperature_2m, precipitation, cloud_cover,
             wind_speed_10m, shortwave_radiation, direct_radiation, diffuse_radiation, is_day)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            temperature_2m      = VALUES(temperature_2m),
            precipitation       = VALUES(precipitation),
            cloud_cover         = VALUES(cloud_cover),
            wind_speed_10m      = VALUES(wind_speed_10m),
            shortwave_radiation = VALUES(shortwave_radiation),
            direct_radiation    = VALUES(direct_radiation),
            diffuse_radiation   = VALUES(diffuse_radiation),
            is_day              = VALUES(is_day)
    """

    rows = [
        (
            location_id, times[i],
            hourly["temperature_2m"][i], hourly["precipitation"][i],
            hourly["cloud_cover"][i], hourly["wind_speed_10m"][i],
            hourly["shortwave_radiation"][i], hourly["direct_radiation"][i],
            hourly["diffuse_radiation"][i], hourly["is_day"][i],
        )
        for i in range(len(times))
    ]
    cursor.executemany(sql, rows)
    return len(rows)