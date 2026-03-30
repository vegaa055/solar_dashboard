"""
tests/test_analytics.py

Unit tests for the analytics service.
Run with: pytest tests/ -v
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# We test the pure functions that don't need a DB connection
from app.services.analytics import daily_summary, rolling_irradiance, irradiance_trend


# ---- Fixtures -------------------------------------------------------

def make_hourly_df(days=7, base_ghi=500.0):
    """Generate a synthetic hourly DataFrame for testing."""
    start = datetime(2025, 6, 1, 0, 0)
    times = [start + timedelta(hours=i) for i in range(days * 24)]
    # Simulate a sine-curve GHI (daylight hours higher, night = 0)
    hours = np.array([t.hour for t in times])
    ghi = np.where(
        (hours >= 6) & (hours <= 18),
        base_ghi * np.sin(np.pi * (hours - 6) / 12),
        0.0
    )
    df = pd.DataFrame({
        "forecast_time": pd.to_datetime(times),
        "shortwave_radiation": ghi,
        "direct_radiation": ghi * 0.8,
        "diffuse_radiation": ghi * 0.2,
        "temperature_2m": 30.0 + np.random.uniform(-2, 2, len(times)),
        "precipitation": 0.0,
        "cloud_cover": np.random.randint(0, 30, len(times)),
        "wind_speed_10m": 15.0,
        "is_day": (hours >= 6) & (hours <= 18),
    })
    return df


# ---- Tests ----------------------------------------------------------

class TestDailySummary:
    def test_returns_one_row_per_day(self):
        df = make_hourly_df(days=7)
        summary = daily_summary(df, "forecast_time")
        assert len(summary) == 7

    def test_peak_ghi_is_max_of_hourly(self):
        df = make_hourly_df(days=3)
        summary = daily_summary(df, "forecast_time")
        for _, row in summary.iterrows():
            day_df = df[df["forecast_time"].dt.date == row["date"]]
            assert row["peak_ghi"] == pytest.approx(day_df["shortwave_radiation"].max(), rel=1e-3)

    def test_zero_precipitation_totals(self):
        df = make_hourly_df(days=5)
        summary = daily_summary(df, "forecast_time")
        assert (summary["total_precip"] == 0.0).all()

    def test_handles_single_day(self):
        df = make_hourly_df(days=1)
        summary = daily_summary(df, "forecast_time")
        assert len(summary) == 1


class TestRollingIrradiance:
    def test_column_added(self):
        df = make_hourly_df(days=2)
        result = rolling_irradiance(df, "forecast_time", window_hours=6)
        assert "ghi_rolling" in result.columns

    def test_rolling_never_exceeds_max(self):
        df = make_hourly_df(days=3)
        result = rolling_irradiance(df, "forecast_time")
        assert (result["ghi_rolling"] <= result["shortwave_radiation"].max() + 0.01).all()

    def test_original_df_not_mutated(self):
        df = make_hourly_df(days=2)
        original_cols = set(df.columns)
        rolling_irradiance(df, "forecast_time")
        assert set(df.columns) == original_cols  # no side effects


class TestIrradianceTrend:
    def test_returns_dict_with_expected_keys(self):
        df = make_hourly_df(days=7)
        result = irradiance_trend(df, "forecast_time")
        assert result is not None
        assert "slope_per_day" in result
        assert "r_squared" in result
        assert "trend" in result

    def test_trend_label_is_valid(self):
        df = make_hourly_df(days=7)
        result = irradiance_trend(df, "forecast_time")
        assert result["trend"] in ("increasing", "decreasing", "stable")

    def test_returns_none_for_insufficient_data(self):
        df = make_hourly_df(days=1)  # Only 1 day -> 1 summary row -> < 3 needed
        result = irradiance_trend(df, "forecast_time")
        assert result is None

    def test_r_squared_between_0_and_1(self):
        df = make_hourly_df(days=7)
        result = irradiance_trend(df, "forecast_time")
        assert 0.0 <= result["r_squared"] <= 1.0
