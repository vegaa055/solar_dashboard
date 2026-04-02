<<<<<<< HEAD
"""
run.py - Entry point for development server.
Production: use gunicorn (see docker-compose.yml)
"""
=======
"""run.py — Development entry point."""
>>>>>>> c6a60c353a8e7b2f44847ab8342dacb2ac90caf3
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
