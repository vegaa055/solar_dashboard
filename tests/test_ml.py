"""
tests/test_ml.py

Unit tests for the ML service.
Tests feature engineering and persistence model — no DB or trained model needed.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.services.ml import build_features, persistence_forecast, FEATURE_NAMES


def make_actuals_df(days=14):
    """Synthetic hourly actuals DataFrame for testing."""
    start = datetime(2025, 6, 1)
    times = [start + timedelta(hours=i) for i in range(days * 24)]
    hours = np.array([t.hour for t in times])
    ghi = np.where(
        (hours >= 6) & (hours <= 18),
        800 * np.sin(np.pi * (hours - 6) / 12),
        0.0,
    )
    return pd.DataFrame({
        "observation_time": pd.to_datetime(times),
        "shortwave_radiation": ghi,
        "cloud_cover":         np.random.randint(0, 40, len(times)),
        "temperature_2m":      30 + np.random.uniform(-3, 3, len(times)),
        "wind_speed_10m":      15 + np.random.uniform(-5, 5, len(times)),
        "is_day":              ((hours >= 6) & (hours <= 18)).astype(int),
    })


class TestBuildFeatures:
    def test_returns_all_expected_columns(self):
        df = make_actuals_df(3)
        X = build_features(df, "observation_time")
        for col in FEATURE_NAMES:
            assert col in X.columns, f"Missing feature: {col}"

    def test_no_nan_on_clean_input(self):
        df = make_actuals_df(7)
        X = build_features(df, "observation_time")
        assert not X.isnull().any().any(), "Unexpected NaN in features"

    def test_row_count_preserved(self):
        df = make_actuals_df(5)
        X = build_features(df, "observation_time")
        assert len(X) == len(df)

    def test_sin_cos_hour_in_unit_range(self):
        df = make_actuals_df(2)
        X = build_features(df, "observation_time")
        assert X["sin_hour"].between(-1, 1).all()
        assert X["cos_hour"].between(-1, 1).all()

    def test_is_day_binary(self):
        df = make_actuals_df(3)
        X = build_features(df, "observation_time")
        assert set(X["is_day"].unique()).issubset({0, 1})

    def test_hour_range(self):
        df = make_actuals_df(3)
        X = build_features(df, "observation_time")
        assert X["hour"].between(0, 23).all()

    def test_handles_missing_weather_data(self):
        """NaN weather values should be filled, not propagated."""
        df = make_actuals_df(3)
        df.loc[10:20, "cloud_cover"] = np.nan
        df.loc[30:40, "temperature_2m"] = np.nan
        X = build_features(df, "observation_time")
        assert not X[["cloud_cover", "temperature_2m"]].isnull().any().any()


class TestPersistenceForecast:
    def test_first_24_are_nan(self):
        df = make_actuals_df(5)
        p = persistence_forecast(df, "observation_time")
        assert np.all(np.isnan(p[:24]))

    def test_values_after_24_match_lag(self):
        df = make_actuals_df(5)
        p = persistence_forecast(df, "observation_time")
        ghi = df["shortwave_radiation"].values
        np.testing.assert_array_almost_equal(p[24:], ghi[:-24])

    def test_output_length_matches_input(self):
        df = make_actuals_df(7)
        p = persistence_forecast(df, "observation_time")
        assert len(p) == len(df)

    def test_non_negative_after_lag(self):
        """GHI is always >= 0 so persistence should be too."""
        df = make_actuals_df(4)
        p = persistence_forecast(df, "observation_time")
        assert np.nanmin(p) >= 0
