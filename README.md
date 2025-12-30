# Calgary Traffic Incidents 2024 API

Django + Django REST Framework API for Calgary (YYC) 2024 traffic incidents, enriched with daily weather data from five nearby stations. Ships with loaders, OpenAPI docs, and a small test suite.

## Quick Start

- Prereqs: Python 3.12+ (3.13 preferred), `pip`
- Clone this repo, then from the repo root:

```
python -m venv .venv
./.venv/Scripts/Activate.ps1   # PowerShell
pip install -U pip
pip install -r requirements.txt

# First run: create DB schema
python manage.py migrate

# Load datasets (expects CSVs under Data/)
python manage.py load_weather --dir Data/
python manage.py load_collisions --csv Data/Traffic_Incidents_*.csv
python manage.py build_city_weather

# Run server
python manage.py runserver 127.0.0.1:8000
```

- Open: `http://127.0.0.1:8000/`
  - Swagger UI: `/docs/`
  - Redoc: `/redoc/`
  - OpenAPI JSON: `/api/schema/`

## Example Endpoints

- List collisions: `/api/v1/collisions` (supports pagination, search, ordering)
- Filtered list: `/api/v1/collisions?from_date=2024-01-01&to_date=2024-12-31&quadrant=NE`
- Detail by ID: `/api/v1/collisions/{collision_id}`
- Create flag: POST `/api/v1/flags` with JSON `{ "collision": "{collision_id}", "note": "text" }`
  - Flags support retrieve/update/delete at `/api/v1/flags/{id}` (use Swagger UI to try PUT/PATCH/DELETE).
- Stats:
  - Monthly: `/api/v1/stats/monthly-trend`
  - By hour: `/api/v1/stats/by-hour?commute=am`
  - Weekday: `/api/v1/stats/weekday`
  - Quadrants: `/api/v1/stats/quadrant-share`
  - Top intersections: `/api/v1/stats/top-intersections?limit=10`
  - By weather: `/api/v1/stats/by-weather`
- Near collisions: `/api/v1/collisions/near?lat=51.045&lon=-114.06&radius_km=1.5`

Note: `weather_day_city` filter accepts dry|wet|snowy, e.g. `/api/v1/collisions?weather_day_city=snowy` (applies to stats too).

Collision IDs note: Collision IDs are string keys from the source CSV (not sequential integers). Use the exact `collision_id` shown in list responses and in the example link on the home page.

### cURL examples (Flags CRUD)

```
# Create a flag (replace <collision_id>)
curl -s -X POST http://127.0.0.1:8000/api/v1/flags/ \
  -H "Content-Type: application/json" \
  -d '{"collision":"<collision_id>","note":"hazard present"}'

# Update the flag note (replace <id>)
curl -s -X PATCH http://127.0.0.1:8000/api/v1/flags/<id>/ \
  -H "Content-Type: application/json" \
  -d '{"note":"updated note"}'

# Delete the flag
curl -s -X DELETE http://127.0.0.1:8000/api/v1/flags/<id>/
```

## Datasets

Place CSVs in `Data/` at repo root.
- Traffic: `Traffic_Incidents_*.csv` (City of Calgary)
- Weather: `en_climate_daily_AB_*_2024_P1D.csv` (Environment Canada)

## Testing

```
pytest -q
```

Tests cover models (uniques), loaders (tiny CSV fixtures), API list/detail/flags/filters, stats, and near.

## OpenAPI Schema Export

Export `schema.yaml` for submission or documentation:

```
python manage.py spectacular --file schema.yaml
```

## Admin Access

Create a local superuser for browsing admin:

```
python manage.py createsuperuser
```

Include admin credentials in the report (do not commit credentials).

## Submission Notes

- Keep `db.sqlite3` out of Git during development.
- For the submission/production branch: run loaders, then include the pre-seeded `db.sqlite3` to ease grading (force-add if necessary). Do not include secrets.
- Include `schema.yaml` export and ensure `/` links to `/docs` for full marks.

## Structure

- `calgary_collisions/` – project (settings/urls)
- `core/` – models + management commands (loaders, city aggregate)
- `api/` – serializers, viewsets, filters, URLs, views (stats, near)
- `templates/` – index page linking to docs and examples
- `tests/` – pytest + factories
- `Data/` – CSVs (tracked)

## License

MIT (see LICENSE)
