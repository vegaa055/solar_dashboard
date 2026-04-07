"""
app/services/ml.py

XGBoost solar irradiance (GHI) forecast with:
  - Persistence model as naive baseline
  - Forecast skill score vs persistence
  - Feature importance
  - Joblib model persistence across container restarts
  - Cross-validation on small datasets

Model: predicts hourly shortwave_radiation (GHI, W/m²)
Features: hour, month, day_of_year, cloud_cover, temperature_2m,
          wind_speed_10m, is_day, sin/cos hour encoding
"""
import os
import logging
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta
from pathlib import Path

from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor



logger = logging.getLogger(__name__)

def get_conn():
    """Lazy import — avoids DB dependency at module load time (e.g. during tests)."""
    from app.db import get_conn as _gc
    return _gc()

# Where trained models are stored inside the container
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Minimum rows needed to attempt training
MIN_TRAIN_ROWS = 48   # 2 days of hourly data
MIN_GOOD_ROWS  = 336  # 14 days — model starts generalizing well here


# ── Feature engineering ────────────────────────────────────────────

def build_features(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """
    Engineer time and weather features from a raw hourly DataFrame.
    Returns a feature DataFrame aligned to the input index.
    """
    df = df.copy()
    t = pd.to_datetime(df[time_col])

    hour        = t.dt.hour
    doy         = t.dt.dayofyear
    month       = t.dt.month

    features = pd.DataFrame({
        # Cyclical time encodings — avoids discontinuity at midnight/year-end
        "sin_hour":    np.sin(2 * np.pi * hour / 24),
        "cos_hour":    np.cos(2 * np.pi * hour / 24),
        "sin_doy":     np.sin(2 * np.pi * doy  / 365),
        "cos_doy":     np.cos(2 * np.pi * doy  / 365),
        "sin_month":   np.sin(2 * np.pi * month / 12),
        "cos_month":   np.cos(2 * np.pi * month / 12),

        # Raw time (tree models can use these directly too)
        "hour":        hour.values,
        "month":       month.values,
        "day_of_year": doy.values,

        # Weather features
        "cloud_cover":      df["cloud_cover"].fillna(0).values,
        "temperature_2m":   df["temperature_2m"].fillna(20).values,
        "wind_speed_10m":   df["wind_speed_10m"].fillna(0).values,
        "is_day":           df["is_day"].fillna(0).astype(int).values,
    }, index=df.index)

    return features


FEATURE_NAMES = [
    "sin_hour", "cos_hour", "sin_doy", "cos_doy", "sin_month", "cos_month",
    "hour", "month", "day_of_year",
    "cloud_cover", "temperature_2m", "wind_speed_10m", "is_day",
]

FEATURE_LABELS = {
    "sin_hour":       "Hour (sin)",
    "cos_hour":       "Hour (cos)",
    "sin_doy":        "Day of Year (sin)",
    "cos_doy":        "Day of Year (cos)",
    "sin_month":      "Month (sin)",
    "cos_month":      "Month (cos)",
    "hour":           "Hour of Day",
    "month":          "Month",
    "day_of_year":    "Day of Year",
    "cloud_cover":    "Cloud Cover (%)",
    "temperature_2m": "Temperature (°C)",
    "wind_speed_10m": "Wind Speed (km/h)",
    "is_day":         "Is Daytime",
}


# ── Persistence model ──────────────────────────────────────────────

def persistence_forecast(df: pd.DataFrame, time_col: str) -> np.ndarray:
    """
    Naive persistence baseline: GHI(t) ≈ GHI(t - 24h).
    This is the standard meteorological baseline for forecast skill.
    Returns array aligned to df index (NaN for first 24 rows).
    """
    ghi = df["shortwave_radiation"].values
    persistence = np.empty_like(ghi, dtype=float)
    persistence[:24] = np.nan
    persistence[24:] = ghi[:-24]
    return persistence


# ── Model path helpers ─────────────────────────────────────────────

def _model_path(location_id: int) -> Path:
    return MODEL_DIR / f"xgb_loc{location_id}.joblib"

def _meta_path(location_id: int) -> Path:
    return MODEL_DIR / f"xgb_loc{location_id}_meta.joblib"


# ── Training ───────────────────────────────────────────────────────

def train(location_id: int) -> dict:
    """
    Fetch historical actuals, engineer features, train XGBoost model.
    Returns training metrics including CV RMSE, skill score vs persistence,
    and feature importances.
    """
    # ── Pull actuals from DB ──
    sql = """
        SELECT observation_time, shortwave_radiation, cloud_cover,
               temperature_2m, wind_speed_10m, is_day
        FROM actuals
        WHERE location_id = %s
          AND shortwave_radiation IS NOT NULL
        ORDER BY observation_time
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=(location_id,))

    n_rows = len(df)
    logger.info(f"[ml] Training location {location_id} — {n_rows} rows available")

    if n_rows < MIN_TRAIN_ROWS:
        return {
            "status": "insufficient_data",
            "message": f"Need at least {MIN_TRAIN_ROWS} rows ({MIN_TRAIN_ROWS//24} days). Have {n_rows}.",
            "rows_available": n_rows,
        }

    # ── Feature engineering ──
    X = build_features(df, "observation_time")
    y = df["shortwave_radiation"].values

    # Drop NaN rows (from feature engineering edge cases)
    mask = ~np.isnan(y) & ~X.isnull().any(axis=1)
    X, y = X[mask], y[mask]

    # ── XGBoost model ──
    xgb = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    # Cross-validation (3-fold on small datasets, 5-fold otherwise)
    n_folds = 3 if len(X) < 500 else 5
    cv = KFold(n_splits=n_folds, shuffle=False)  # no shuffle — time series order matters
    cv_scores = cross_val_score(xgb, X, y, cv=cv,
                                scoring="neg_root_mean_squared_error")
    cv_rmse = float(-cv_scores.mean().round(2))
    cv_std  = float(cv_scores.std().round(2))

    # Final fit on all data
    xgb.fit(X, y)

    # ── Persistence baseline RMSE ──
    persistence = persistence_forecast(df[mask.values], "observation_time")
    valid_mask  = ~np.isnan(persistence)
    if valid_mask.sum() > 0:
        p_rmse = float(np.sqrt(mean_squared_error(
            y[valid_mask], persistence[valid_mask]
        )).round(2))
    else:
        p_rmse = None

    # ── Skill score ──
    skill_score = None
    if p_rmse and p_rmse > 0:
        skill_score = round(1 - (cv_rmse / p_rmse), 3)

    # ── Feature importances ──
    importances = dict(zip(
        FEATURE_NAMES,
        [round(float(v), 4) for v in xgb.feature_importances_]
    ))
    # Sort descending
    importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

    # ── Persist model + metadata ──
    joblib.dump(xgb, _model_path(location_id))

    meta = {
        "location_id":       location_id,
        "trained_at":        datetime.utcnow().isoformat(),
        "rows_used":         int(mask.sum()),
        "cv_rmse_wm2":       cv_rmse,
        "cv_rmse_std":       cv_std,
        "cv_folds":          n_folds,
        "persistence_rmse":  p_rmse,
        "skill_score":       skill_score,
        "feature_importance": importances,
        "data_warning":      n_rows < MIN_GOOD_ROWS,
        "data_warning_msg":  (
            f"Only {n_rows} rows ({n_rows//24} days). Model accuracy improves "
            f"significantly with 14+ days of data."
        ) if n_rows < MIN_GOOD_ROWS else None,
    }
    joblib.dump(meta, _meta_path(location_id))

    logger.info(
        f"[ml] Training complete — loc {location_id} | "
        f"CV RMSE: {cv_rmse} W/m² | Skill: {skill_score}"
    )
    return {"status": "ok", **meta}


# ── Inference ──────────────────────────────────────────────────────

def predict_forecast(location_id: int, days: int = 3) -> dict:
    """
    Generate ML GHI predictions for upcoming forecast hours.
    Uses the stored XGBoost model and forecast table weather features.
    Returns hourly predictions aligned to forecast_time.
    """
    model_path = _model_path(location_id)
    meta_path  = _meta_path(location_id)

    if not model_path.exists():
        return {"status": "no_model", "message": "Model not trained yet. Call /api/ml/train first."}

    xgb  = joblib.load(model_path)
    meta = joblib.load(meta_path)

    # Pull forecast weather features
    sql = """
        SELECT forecast_time, cloud_cover, temperature_2m,
               wind_speed_10m, is_day,
               shortwave_radiation
        FROM forecasts
        WHERE location_id = %s
          AND forecast_time >= NOW()
          AND forecast_time <= NOW() + INTERVAL %s DAY
        ORDER BY forecast_time
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=(location_id, days))

    if df.empty:
        return {"status": "no_forecast_data", "message": "No forecast data in DB."}

    X = build_features(df, "forecast_time")
    preds = xgb.predict(X)
    preds = np.clip(preds, 0, None)  # GHI can't be negative

    results = []
    for i, row in df.iterrows():
        results.append({
            "forecast_time":        str(row["forecast_time"])[:16],
            "ml_ghi":               round(float(preds[i - df.index[0]]), 2),
            "openmeteo_ghi":        row["shortwave_radiation"],
        })

    return {
        "status": "ok",
        "location_id": location_id,
        "model_trained_at": meta.get("trained_at"),
        "skill_score":      meta.get("skill_score"),
        "data_warning":     meta.get("data_warning"),
        "data_warning_msg": meta.get("data_warning_msg"),
        "predictions":      results,
    }


def get_status(location_id: int) -> dict:
    """Return metadata about the current trained model for a location."""
    meta_path = _meta_path(location_id)
    if not meta_path.exists():
        return {"status": "untrained", "location_id": location_id}
    meta = joblib.load(meta_path)
    meta["status"] = "trained"
    return meta


def train_all_locations():
    """Retrain models for all locations — called by APScheduler."""
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM locations")
        locations = cursor.fetchall()
        cursor.close()

    results = []
    for loc in locations:
        logger.info(f"[ml] Scheduled retraining: {loc['name']}")
        result = train(loc["id"])
        results.append({"location": loc["name"], "status": result.get("status"), 
                        "skill_score": result.get("skill_score")})
    return results
