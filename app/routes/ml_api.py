"""
app/routes/ml_api.py

ML forecast endpoints.

POST /api/ml/train?location_id=1       Train / retrain XGBoost model
GET  /api/ml/forecast?location_id=1&days=3   ML predictions for next N days
GET  /api/ml/status?location_id=1      Model metadata, skill score, feature importance
GET  /api/ml/compare?location_id=1     3-way comparison: ML vs Open-Meteo vs Actual
"""
import math
from flask import Blueprint, request, jsonify
from app.services import ml
from app.db import get_conn
import pandas as pd

ml_api = Blueprint("ml_api", __name__, url_prefix="/api/ml")


def _error(msg, code=400):
    return jsonify({"error": msg}), code


def _require_location_id():
    lid = request.args.get("location_id", type=int)
    if lid is None:
        return None, _error("location_id is required")
    return lid, None


def _sanitize(obj):
    """
    Recursively replace float NaN/Inf with None so Flask's jsonify
    produces valid JSON. Python's json module emits literal NaN which
    the JSON spec and browsers both reject.
    """
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


@ml_api.route("/train", methods=["POST"])
def train():
    lid, err = _require_location_id()
    if err:
        return err
    result = ml.train(lid)
    code = 200 if result.get("status") == "ok" else 422
    return jsonify(_sanitize(result)), code


@ml_api.route("/forecast")
def forecast():
    lid, err = _require_location_id()
    if err:
        return err
    days = min(max(request.args.get("days", default=3, type=int), 1), 7)
    result = ml.predict_forecast(lid, days)
    return jsonify(_sanitize(result))


@ml_api.route("/status")
def status():
    lid, err = _require_location_id()
    if err:
        return err
    return jsonify(_sanitize(ml.get_status(lid)))


@ml_api.route("/compare")
def compare():
    """
    3-way daily comparison: Open-Meteo forecast vs ML forecast vs Actuals.
    Used by the frontend compare chart.
    """
    lid, err = _require_location_id()
    if err:
        return err

    # Open-Meteo daily avg forecast
    fcst_sql = """
        SELECT DATE(forecast_time) AS day,
               AVG(shortwave_radiation) AS openmeteo_ghi
        FROM forecasts
        WHERE location_id = %s
          AND forecast_time >= NOW() - INTERVAL 7 DAY
        GROUP BY day ORDER BY day
    """
    # Actuals daily avg
    actual_sql = """
        SELECT DATE(observation_time) AS day,
               AVG(shortwave_radiation) AS obs_ghi
        FROM actuals
        WHERE location_id = %s
          AND observation_time >= NOW() - INTERVAL 7 DAY
        GROUP BY day ORDER BY day
    """
    with get_conn() as conn:
        f_df = pd.read_sql(fcst_sql,   conn, params=(lid,))
        a_df = pd.read_sql(actual_sql, conn, params=(lid,))

    # ML predictions (hourly → aggregate to daily avg)
    ml_result = ml.predict_forecast(lid, days=7)
    ml_daily  = {}
    if ml_result.get("status") == "ok":
        preds = ml_result["predictions"]
        ml_df = pd.DataFrame(preds)
        ml_df["date"] = pd.to_datetime(ml_df["forecast_time"]).dt.date
        ml_daily = ml_df.groupby("date")["ml_ghi"].mean().round(2).to_dict()

    # Merge — outer join produces NaN for missing days, sanitized below
    merged = pd.merge(f_df, a_df, on="day", how="outer").sort_values("day")
    merged["day"] = merged["day"].astype(str)
    merged["ml_ghi"] = merged["day"].apply(
        lambda d: round(ml_daily.get(pd.to_datetime(d).date(), None) or 0, 2)
        if ml_daily else None
    )

    model_status = ml.get_status(lid)

    payload = {
        "status":             "ok",
        "model_status":       model_status.get("status"),
        "skill_score":        model_status.get("skill_score"),
        "cv_rmse_wm2":        model_status.get("cv_rmse_wm2"),
        "persistence_rmse":   model_status.get("persistence_rmse"),
        "data_warning":       model_status.get("data_warning"),
        "data_warning_msg":   model_status.get("data_warning_msg"),
        "feature_importance": model_status.get("feature_importance"),
        "trained_at":         model_status.get("trained_at"),
        "rows_used":          model_status.get("rows_used"),
        "daily":              merged.to_dict(orient="records"),
    }

    return jsonify(_sanitize(payload))