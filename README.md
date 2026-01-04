# Calgary Traffic Incidents 2024 API

REST API (Django + DRF) for Calgary (YYC) 2024 traffic incidents, enriched with city daily weather derived from nearby stations. Includes loaders, OpenAPI docs, a dashboard, and tests.

## Quick Start

- Python 3.12+ (3.13 preferred)
- From repo root:

```
python -m venv .venv
./.venv/Scripts/Activate.ps1  # PowerShell
pip install -U pip
pip install -r requirements.txt

# Create DB schema
python manage.py migrate

# Load datasets (place CSVs in Data/)
python manage.py load_weather --dir Data/
python manage.py load_collisions --csv Data/Traffic_Incidents_*.csv
python manage.py build_city_weather

# Run the server
python manage.py runserver 127.0.0.1:8000
```

Open: `http://127.0.0.1:8000/`

## Homepage

- Overview (single panel)
  - Assessment toggle (cookie-based)
  - Status (record counts + DB engine)
  - Run Info (on when assessment is on: OS, Python, Django/DRF, setup/test snippets)
  - Admin (link; credentials are in the report’s Reproducibility section)
  - Docs (Swagger, Redoc, OpenAPI JSON)
- Endpoints: quick links to common API calls
- Dashboard: filters, charts, top intersections, paginated collisions, near collisions

Tip: Assessment mode only reveals diagnostic context; API behavior is unchanged. It defaults off for safety and can be toggled from the homepage.

## API Examples

- List: `/api/v1/collisions`
- Filter: `/api/v1/collisions?from_date=2024-01-01&to_date=2024-12-31&quadrant=NE`
- Detail: `/api/v1/collisions/{collision_id}` (IDs are strings from the source CSV)
- Flags: `/api/v1/flags` (+ CRUD via Swagger UI)
- Stats: `/api/v1/stats/monthly-trend`, `/api/v1/stats/by-hour?commute=am`, `/api/v1/stats/weekday`, `/api/v1/stats/quadrant-share`, `/api/v1/stats/top-intersections?limit=10`, `/api/v1/stats/by-weather`
- Near: `/api/v1/collisions/near?lat=51.045&lon=-114.06&radius_km=1.5`

`weather_day_city` accepts dry|wet|snowy and applies to list and stats.

### cURL (Flags)

```
# Create
curl -s -X POST http://127.0.0.1:8000/api/v1/flags/ \
  -H "Content-Type: application/json" \
  -d '{"collision":"<collision_id>","note":"hazard"}'

# Update
curl -s -X PATCH http://127.0.0.1:8000/api/v1/flags/<id>/ \
  -H "Content-Type: application/json" \
  -d '{"note":"updated note"}'

# Delete
curl -s -X DELETE http://127.0.0.1:8000/api/v1/flags/<id>/
```

## Data

Put CSVs under `Data/`:
- Traffic: `Traffic_Incidents_*.csv` (City of Calgary)
- Weather: `en_climate_daily_AB_*_2024_P1D.csv` (Environment Canada)

## Testing

```
pytest -q
```

Generates test and (if enabled) coverage reports in `reports/`.

## Schema

Export OpenAPI to `schema.yaml`:

```
python manage.py spectacular --file schema.yaml
```

## Admin

Create a local superuser for browsing admin:

```
python manage.py createsuperuser
```

Public credentials are not displayed on the homepage. See the report’s Reproducibility section.

## Scripts

- Smoke check: `python scripts/smoke_check.py`
  - A small root stub `smoke_check.py` remains for compatibility (imports and calls the script’s main when run directly).

## Repository Layout

- `calgary_collisions/` – project config (settings/urls)
- `core/` – models and management commands (loaders, city aggregate)
- `api/` – serializers, filters, viewsets, views (stats, near), URLs
- `templates/` – homepage template
- `static/` – dashboard assets
- `tests/` – pytest suite + factories
- `scripts/` – utility scripts (e.g., smoke_check)
- `Data/` – CSVs (local only, not required for tests)

## Notes

- Keep secrets out of the repo. For local development, use environment variables.
- Assessment mode is cookie-based and defaults off; toggle from the homepage.
