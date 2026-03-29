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