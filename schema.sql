-- =============================================================
-- Solar Forecast Dashboard - Database Schema
-- =============================================================

CREATE DATABASE IF NOT EXISTS solar_dashboard;
USE solar_dashboard;

-- Locations we track (easily extensible)
CREATE TABLE IF NOT EXISTS locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    lat         DECIMAL(9,6) NOT NULL,
    lon         DECIMAL(9,6) NOT NULL,
    elevation   INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_latlon (lat, lon)
);

-- Hourly forecast data fetched from Open-Meteo
CREATE TABLE IF NOT EXISTS forecasts (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    location_id         INT NOT NULL,
    forecast_time       DATETIME NOT NULL,
    fetched_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    temperature_2m      DECIMAL(5,2),
    precipitation       DECIMAL(6,2),
    cloud_cover         TINYINT UNSIGNED,
    wind_speed_10m      DECIMAL(6,2),
    shortwave_radiation DECIMAL(8,2),    -- W/m² GHI
    direct_radiation    DECIMAL(8,2),    -- W/m² DNI proxy
    diffuse_radiation   DECIMAL(8,2),    -- W/m² DHI
    is_day              TINYINT(1),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    UNIQUE KEY uq_forecast (location_id, forecast_time)
);

-- Actual observed values for forecast vs actual comparison
CREATE TABLE IF NOT EXISTS actuals (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    location_id         INT NOT NULL,
    observation_time    DATETIME NOT NULL,
    fetched_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    temperature_2m      DECIMAL(5,2),
    precipitation       DECIMAL(6,2),
    cloud_cover         TINYINT UNSIGNED,
    wind_speed_10m      DECIMAL(6,2),
    shortwave_radiation DECIMAL(8,2),
    direct_radiation    DECIMAL(8,2),
    diffuse_radiation   DECIMAL(8,2),
    is_day              TINYINT(1),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    UNIQUE KEY uq_actual (location_id, observation_time)
);