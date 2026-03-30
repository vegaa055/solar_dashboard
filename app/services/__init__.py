"""
app/__init__.py — Flask application factory with APScheduler background jobs.
"""
import os
import logging
import threading
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
    CORS(app)

    from app.routes.api import api
    app.register_blueprint(api)

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(app.static_folder, path)

    _start_scheduler()
    logger.info("Solar Dashboard app ready.")
    return app


def _start_scheduler():
    from app.services.ingestion import fetch_all_locations
    interval = int(os.getenv("FETCH_INTERVAL_MINUTES", 60))

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=lambda: fetch_all_locations("forecast"),
        trigger="interval", minutes=interval, id="fetch_forecast", replace_existing=True,
    )
    scheduler.add_job(
        func=lambda: fetch_all_locations("historical"),
        trigger="cron", hour=1, minute=0, id="fetch_historical", replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — forecast fetch every {interval} min.")

    def initial_fetch():
        logger.info("Running initial data fetch...")
        fetch_all_locations("historical")
        fetch_all_locations("forecast")
        logger.info("Initial fetch complete.")

    threading.Thread(target=initial_fetch, daemon=True).start()