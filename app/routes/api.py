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