# Solar Forecast Dashboard ☀

A full-stack solar irradiance and weather forecast dashboard for Arizona,
built with Python/Flask, MySQL, Pandas/NumPy/SciPy, and a vanilla JS frontend.

**Stack:** Python · Flask · MySQL · Pandas · NumPy · SciPy · APScheduler · Docker · Chart.js

## Status

🚧 Under active development — see branch history for build progress.

## Overview

The Power Forecasting Group (PFG) use case: ingest hourly weather and solar
irradiance data for Southwest US locations, warehouse it in MySQL, expose it
through a RESTful Flask API, and visualize it in a browser dashboard.

Data source: [Open-Meteo](https://open-meteo.com/) — free, no API key required.
