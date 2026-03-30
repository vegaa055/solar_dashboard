"""
app/routes/api.py — RESTful API routes. All responses JSON.

GET  /api/locations
GET  /api/forecast?location_id=&days=
GET  /api/forecast/daily?location_id=
GET  /api/historical?location_id=&days=
GET  /api/compare?location_id=
GET  /api/trend?location_id=&source=
POST /api/ingest?fetch_type=
GET  /api/ingest/log?limit=
"""
from flask import Blueprint, request, jsonify
from app.db import get_conn
from app.services import ingestion, analytics

api = Blueprint("api", __name__, url_prefix="/api")


def _error(msg, code=400):
    return jsonify({"error": msg}), code


def _require_location_id():
    lid = request.args.get("location_id", type=int)
    if lid is None:
        return None, _error("location_id is required")
    return lid, None


@api.route("/locations")
def list_locations():
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, lat, lon, elevation FROM locations ORDER BY name")
        rows = cursor.fetchall()
        cursor.close()
    return jsonify(rows)


@api.route("/forecast")
def get_forecast():
    lid, err = _require_location_id()
    if err:
        return err
    days = min(max(request.args.get("days", default=7, type=int), 1), 7)
    df = analytics.get_forecast_df(lid, days)
    if df.empty:
        return jsonify({"message": "No forecast data. Trigger /api/ingest first.", "data": []})
    df = analytics.rolling_irradiance(df, "forecast_time")
    df["forecast_time"] = df["forecast_time"].dt.strftime("%Y-%m-%dT%H:%M")
    return jsonify(df.to_dict(orient="records"))


@api.route("/forecast/daily")
def get_forecast_daily():
    lid, err = _require_location_id()
    if err:
        return err
    df = analytics.get_forecast_df(lid, days=7)
    if df.empty:
        return jsonify({"message": "No forecast data yet.", "data": []})
    summary = analytics.daily_summary(df, "forecast_time")
    summary["date"] = summary["date"].astype(str)
    return jsonify(summary.to_dict(orient="records"))


@api.route("/historical")
def get_historical():
    lid, err = _require_location_id()
    if err:
        return err
    days = min(max(request.args.get("days", default=30, type=int), 1), 30)
    df = analytics.get_actuals_df(lid, days)
    if df.empty:
        return jsonify({"message": "No historical data yet.", "data": []})
    df = analytics.rolling_irradiance(df, "observation_time")
    df["observation_time"] = df["observation_time"].dt.strftime("%Y-%m-%dT%H:%M")
    return jsonify(df.to_dict(orient="records"))