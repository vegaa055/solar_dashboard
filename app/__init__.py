"""
app/__init__.py

Flask application factory.
Creates the app, registers blueprints, and starts the APScheduler background job.
"""
import os
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder="../frontend")
    CORS(app)  # Allow local frontend dev without proxy

    # Register API blueprint
    from app.routes.api import api
    app.register_blueprint(api)

    # Serve the frontend dashboard at /
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(app.static_folder, path)

    # Start background scheduler for automatic data ingestion
    _start_scheduler()

    logger.info("Solar Dashboard app created.")
    return app


def _start_scheduler():
    """
    APScheduler runs ingestion on a configurable interval.
    On first startup, immediately fetches forecast + 30-day historical.
    """
    from app.services.ingestion import fetch_all_locations

    interval = int(os.getenv("FETCH_INTERVAL_MINUTES", 60))

    scheduler = BackgroundScheduler(daemon=True)

    # Recurring forecast fetch
    scheduler.add_job(
        func=lambda: fetch_all_locations("forecast"),
        trigger="interval",
        minutes=interval,
        id="fetch_forecast",
        replace_existing=True,
    )

    # Daily historical fetch (runs once per day at 01:00)
    scheduler.add_job(
        func=lambda: fetch_all_locations("historical"),
        trigger="cron",
        hour=1,
        minute=0,
        id="fetch_historical",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started — forecast fetch every {interval} min.")

    # Kick off an immediate fetch so the DB isn't empty on first run
    import threading
    def initial_fetch():
        logger.info("Running initial data fetch...")
        fetch_all_locations("historical")
        fetch_all_locations("forecast")
        logger.info("Initial fetch complete.")

    threading.Thread(target=initial_fetch, daemon=True).start()
