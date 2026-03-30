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

@api.route("/compare")
def compare():
    lid, err = _require_location_id()
    if err:
        return err
    return jsonify(analytics.forecast_vs_actual(lid))


@api.route("/trend")
def trend():
    lid, err = _require_location_id()
    if err:
        return err
    source = request.args.get("source", default="forecast")
    if source == "historical":
        df = analytics.get_actuals_df(lid, days=30)
        time_col = "observation_time"
    else:
        df = analytics.get_forecast_df(lid, days=7)
        time_col = "forecast_time"
    if df.empty:
        return jsonify({"message": "No data available."})
    result = analytics.irradiance_trend(df, time_col)
    if result is None:
        return jsonify({"message": "Need at least 3 days of data."})
    return jsonify(result)


@api.route("/ingest", methods=["POST"])
def trigger_ingest():
    fetch_type = request.args.get("fetch_type", default="forecast")
    if fetch_type not in ("forecast", "historical"):
        return _error("fetch_type must be 'forecast' or 'historical'")
    results = ingestion.fetch_all_locations(fetch_type)
    return jsonify({"fetch_type": fetch_type, "results": results})


@api.route("/ingest/log")
def ingest_log():
    limit = min(request.args.get("limit", default=20, type=int), 100)
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT il.id, l.name as location, il.fetch_type, il.status,
                   il.rows_upserted, il.error_message, il.ran_at
            FROM ingestion_log il
            LEFT JOIN locations l ON l.id = il.location_id
            ORDER BY il.ran_at DESC LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
    for row in rows:
        if row.get("ran_at"):
            row["ran_at"] = str(row["ran_at"])
    return jsonify(rows)