# Solar Forecast Dashboard 🌞

A full-stack solar irradiance and weather forecast dashboard for Arizona locations, built with Python/Flask, MySQL, and a vanilla JS frontend.

**Stack:** Python · Flask · MySQL · Pandas · NumPy · SciPy · APScheduler · Docker · Chart.js

---

## Hosted Web App URL

### Hosted through Hostinger and Dokploy

<a href="https://astralvega.com" linkTarget="_blank">Solar Forecast Dashboard</a>

## Quick Start

### Option A — Docker (recommended)

```bash
# 1. Clone and enter the project
git clone https://github.com/yourusername/solar-dashboard.git
cd solar-dashboard

# 2. Start everything (DB + app)
docker-compose up --build
```

Open `http://localhost:5000` — the app auto-fetches data on first startup.

---

### Option B — Local (no Docker)

**Prerequisites:** Python 3.11+, MySQL 8+

```bash
# 1. Create and activate a virtualenv
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up the database
mysql -u root -p < schema.sql

# 4. Configure environment
cp .env.example .env
# Edit .env: set DB_HOST=localhost, DB_USER, DB_PASSWORD

# 5. Run the app
python run.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover the analytics module (daily aggregation, rolling averages, trend analysis) without requiring a DB connection.

---

## API Reference

| Method | Endpoint                                | Description                 |
| ------ | --------------------------------------- | --------------------------- |
| GET    | `/api/locations`                        | List tracked AZ locations   |
| GET    | `/api/forecast?location_id=1&days=7`    | Hourly 7-day forecast       |
| GET    | `/api/forecast/daily?location_id=1`     | Daily aggregated forecast   |
| GET    | `/api/historical?location_id=1&days=30` | Past 30 days of actuals     |
| GET    | `/api/compare?location_id=1`            | Forecast vs actual RMSE/MAE |
| GET    | `/api/trend?location_id=1`              | GHI linear trend analysis   |
| POST   | `/api/ingest?fetch_type=forecast`       | Manually trigger data fetch |
| GET    | `/api/ingest/log`                       | View ingestion history      |

---

## Project Structure

```
solar_dashboard/
├── app/
│   ├── __init__.py          # App factory + scheduler
│   ├── db.py                # DB connection pool
│   ├── routes/
│   │   └── api.py           # REST API endpoints
│   └── services/
│       ├── ingestion.py     # Open-Meteo fetch + upsert
│       └── analytics.py     # Pandas/NumPy/SciPy processing
├── frontend/
│   └── index.html           # Dashboard UI (Chart.js)
├── tests/
│   └── test_analytics.py    # pytest unit tests
├── schema.sql               # MySQL schema + seed data
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .github/workflows/ci.yml # GitHub Actions CI
```

---

## Data Source

[Open-Meteo](https://open-meteo.com/) — free, no API key required. Provides hourly solar irradiance (GHI, DNI, DHI), temperature, cloud cover, precipitation, and wind speed for any coordinates.

---

## Extending This Project

Ideas for next steps:

- **ML forecasting**: Train a scikit-learn regression on historical GHI + weather features to produce an independent forecast, then compare against Open-Meteo
- **More locations**: Add `INSERT INTO locations` rows for any lat/lon
- **Power output estimate**: Add a simple W = GHI × panel_area × efficiency calculation to model actual solar panel output
- **Kubernetes**: Replace docker-compose with a K8s manifest (relevant to the preferred qualifications!)
- **Alerts**: Email/webhook when forecast shows unusually low irradiance
