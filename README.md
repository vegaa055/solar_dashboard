# Solar Forecast Dashboard ☀

A full-stack solar irradiance and weather forecast dashboard for Arizona,
built with Python/Flask, MySQL, Pandas/NumPy/SciPy, and a vanilla JS frontend.

**Stack:** Python · Flask · MySQL · Pandas · NumPy · SciPy · APScheduler · Docker · Chart.js

## Status

🚧 Under active development.

## Overview

The Power Forecasting Group (PFG) use case: ingest hourly weather and solar
irradiance data for Southwest US locations, warehouse it in MySQL, expose it
through a RESTful Flask API, and visualize it in a browser dashboard.

Data source: [Open-Meteo](https://open-meteo.com/) — free, no API key required.

### Docker (recommended)
```bash
git clone https://github.com/vegaa055/solar-forecast-dashboard.git
cd solar-forecast-dashboard
docker-compose up --build
```
Open `http://localhost:5000` — data fetches automatically on first run.

### Local
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
mysql -u root -p < schema.sql
cp .env.example .env   # edit DB credentials
python run.py
```

## Tests
```bash
pytest tests/ -v
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/locations` | List tracked AZ locations |
| GET | `/api/forecast?location_id=1&days=7` | Hourly forecast |
| GET | `/api/forecast/daily?location_id=1` | Daily aggregated forecast |
| GET | `/api/historical?location_id=1&days=30` | Historical actuals |
| GET | `/api/compare?location_id=1` | Forecast vs actual RMSE/MAE |
| GET | `/api/trend?location_id=1` | GHI linear trend |
| POST | `/api/ingest?fetch_type=forecast` | Manual ingest trigger |
| GET | `/api/ingest/log` | Ingestion history |

## Project Structure
```
├── app/
│   ├── __init__.py          # App factory + APScheduler
│   ├── db.py                # Connection pool
│   ├── routes/api.py        # REST endpoints
│   └── services/
│       ├── ingestion.py     # Open-Meteo fetch + upsert
│       └── analytics.py     # Pandas/NumPy/SciPy processing
├── frontend/index.html      # Chart.js dashboard
├── tests/test_analytics.py  # pytest unit tests
├── schema.sql               # MySQL schema + seed data
├── docker-compose.yml
├── Dockerfile
└── .github/workflows/ci.yml
```

## Data Source
[Open-Meteo](https://open-meteo.com/) — free, no API key required.
Provides hourly GHI, DNI, DHI, temperature, cloud cover, wind, and precipitation.

## Extending This Project
- Add scikit-learn regression for an independent ML forecast layer
- Add `/api/export?format=csv` for sponsor data delivery
- Add more locations via `INSERT INTO locations`
- Migrate docker-compose to Kubernetes (K8s manifests)