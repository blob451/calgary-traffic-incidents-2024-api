# Implementation Log (Stages 1–4)

This document summarizes the work completed in Stages 1–4, verification performed for each change, findings/notes, and any deviations from the original plan. It’s kept under `.gitignore.d/` for local reference only.

---

## Overview

- Repo: `calgary-traffic-incidents-2024-api`
- Python env: local venv with stable dep versions installed; `requirements.txt` pinned.
- Data: CSVs copied into `Data/` at repo root (tracked), row totals under 10k cap.
- Docs: OpenAPI exposed; index page links to docs and example endpoints (placeholders until endpoints exist).

---

## Stage 1 — Scaffold + Configuration

Changes
- Scaffold Django project `calgary_collisions`, apps `core` and `api`.
- Configure `INSTALLED_APPS`: `rest_framework`, `django_filters`, `drf_spectacular`, `core`, `api`.
- Templates: add `templates/` to TEMPLATES.DIRS, create `templates/index.html` (links to docs and example endpoints).
- Static: configure `STATICFILES_DIRS = [BASE_DIR / 'static']` and create `static/`.
- Settings: timezone `America/Edmonton`, `LANGUAGE_CODE = 'en-ca'`, SQLite default DB.
- DRF: pagination (PageNumberPagination, size 50), default filters (django-filter, search, ordering), schema class (drf-spectacular), and default permission `AllowAny`.
- Spectacular: title/description/version.
- Secret key: read `DJANGO_SECRET_KEY` env with safe dev fallback.
- URLs: include `api.urls`, add `/api/schema/`, `/docs/`, `/redoc/`.

Findings/Notes
- Initial `STATICFILES_DIRS` triggered a warning (missing `static/`); resolved by creating the directory.
- Index page renders, contains links to docs and placeholders for API endpoints.

Verification
- `python manage.py check` → OK (after creating `static/`).
- `python manage.py migrate` → OK, `db.sqlite3` created (ignored by Git for dev).
- Manual run sanity (local): index and docs routes available when running dev server.

---

## Stage 2 — Data Models + Migrations

Changes
- Add enums: `Quadrant`, `WeatherDay`.
- Add models:
  - `WeatherStation` (unique `climate_id`, name, lon/lat, index).
  - `WeatherObservation` (FK station, date; temps/precip/snow/gusts; derived `weather_day`, `freeze_day`; unique `(station, date)`; indexes).
  - `CityDailyWeather` (unique `date`; city-level aggregates, index).
  - `Collision` (unique `collision_id`; timestamps + derived date/hour/weekday/month; `quadrant`; lon/lat; `count`; text fields; `intersection_key`; FK `nearest_station`; indexes).
  - `Flag` (FK collision, note, `created_at`).
- Generate and apply `core/migrations/0001_initial.py`.

Findings/Notes
- Model shapes align with plan; indexes match common filters and joins (date/quadrant/nearest_station).
- Fixed `Flag.__str__` to reference `collision.collision_id`.

Verification
- `python manage.py makemigrations core` → created `0001_initial.py`.
- `python manage.py migrate` → applied successfully.
- `python manage.py check` → OK.

---

## Stage 3 — Loaders + Aggregations

Changes
- Add Django management commands under `core/management/commands/`:
  - `load_weather`: upsert `WeatherStation` by `climate_id`; load `WeatherObservation` per-file; derive `weather_day` with improved logic (Snowy > Wet ≥ 0.2mm; DRY only when precip=0 and snow=0; else None) and `freeze_day` (min temp < 0). Handle `M`/blank as NULL and `T` (trace) as 0. Default to `Data/` with `--dir` override. Ensure station creation requires lon/lat; updates only when provided.
  - `build_city_weather`: aggregate per-date across stations; compute `weather_day_city` (Snowy > Wet > Dry), `freeze_day_city` (majority), `t_max_avg`, `t_min_avg`, `precip_any`, `snow_any`, `agreement_ratio`.
  - `load_collisions`: parse collisions CSV(s) (default `Data/Traffic_Incidents_*.csv` or `--csv`); parse local dates; bounds-check lon/lat; normalize `quadrant`; derive `date/hour/weekday/month`, `intersection_key`; compute `nearest_station` (Haversine); upsert by `collision_id`.

Findings/Notes
- `load_weather` station upserts count many “updated” rows (expected, per-row upsert). Dataset size is small so performance is acceptable.
- Timezone handled via `zoneinfo`; `tzdata` included for Windows compatibility.
- All loader behaviors align with normalization rules in plan.

Verification
- `python manage.py load_weather --dir Data` → Stations created/updated and 1,830 observations created.
- `python manage.py build_city_weather` → 366 city-day rows created.
- `python manage.py load_collisions --csv Data/Traffic_Incidents_20251218.csv` → 7,493 collisions created.
- Row totals: traffic 7,493 + weather 1,830 + city-daily 366 ≈ 9,689 (≤ 10,000 requirement).

---

## Stage 4 — API Endpoints (list/detail + POST)

Changes
- Serializers:
  - `CollisionListSerializer` (summary + nested nearest station).
  - `CollisionDetailSerializer` (adds `description`, `intersection_key`, `station_weather`, `city_weather`).
  - `FlagSerializer` (POST by `collision_id` slug).
- Filters:
  - `CollisionFilter`: supports `from_date` (>=), `to_date` (<=), `quadrant`, `weather_day_city` (Dry/Wet/Snowy), `freeze_day_city` (bool), `heavy_rain` (bool), `heavy_snow` (bool), `gust_min` (km/h), `station` (id or climate_id).
  - Search on `description`/`location_text`; ordering on `occurred_at`, `date`, `quadrant`, `count`.
- Views:
  - `CollisionViewSet` (read-only list/retrieve) now uses `collision_id` as lookup field.
  - `FlagViewSet` (create/list).
- URLs:
  - DRF router → `/api/v1/collisions`, `/api/v1/flags`.

Findings/Notes
- Param names are `from_date` and `to_date` (Python identifier constraint). Plan used `from`/`to`. We can optionally add alias handling later.
- Detail serializer inlines station and city weather for the collision’s date as planned.

Verification
- `python manage.py check` → OK.
- Manual smoke tests recommended via dev server (list, detail, create flag) — to be included in Stage 7 tests.

---

## Deviations / Plan Adjustments

- Versions: Using current stable (Django 6.0, DRF 3.16.1) instead of plan’s examples (Django 5.1.x, DRF 3.15.x). Decision approved as “use stable versions in venv”.
- Query params: `from_date`/`to_date` instead of `from`/`to` to satisfy Python identifier rules in FilterSet; consider adding aliases later if desired.
- Secret key handling: added env-based override with dev fallback (good practice, not explicitly called out in plan).
- Minor cosmetic: `Flag.__str__` can be refined later (no functional impact).

---

## Verification Summary

- Lint/checks: `python manage.py check` → OK after Stage 1 and onwards.
- DB schema: `makemigrations`/`migrate` applied successfully (core 0001).
- Loaders: verified with provided CSVs; row totals under cap; idempotent upserts.
- Routes: `/`, `/docs/`, `/redoc/`, `/api/schema/` present; `/api/v1/collisions` and `/api/v1/flags` wired.

---

## Next Steps (Per Plan)

- Stage 6: Implement remaining stats (e.g., near radius).
- Stage 7: Add tests (models, loaders, endpoints) using `pytest` + factories.
- Stage 8: README quick start, OpenAPI export, seed DB on submission branch, report/video.

---

## Stage 5 — Stats Endpoints

Changes
- Added stats APIs under `/api/v1/stats/`:
  - `monthly-trend`: sums `count` by calendar month (1–12) with zero-fill for absent months.
  - `by-hour`: sums `count` by hour (0–23) with optional `commute=am|pm` filters.
  - `weekday`: sums by weekday (0–6, Mon–Sun).
  - `quadrant-share`: counts by `quadrant` (NW/NE/SW/SE/UNK).
  - `top-intersections?limit=10`: ranks by `intersection_key`/`location_text` with cap 100.
  - `by-weather`: maps collision totals by date to `CityDailyWeather.weather_day_city` and aggregates Dry/Wet/Snowy totals.
- Reuse `CollisionFilter` for consistent filtering across stats endpoints.
- Wired routes in `api/urls.py` and implemented APIView classes in `api/views.py`.

Verification
- `python manage.py check` → OK.
- Local manual smoke via dev server recommended (list/detail/stats endpoints respond and shape matches specs).

Notes
- All stats endpoints respect the same filters as `/api/v1/collisions` (date range, quadrant, weather conditions, gust threshold, station, text search for relevant ones).
- `near` endpoint remains for Stage 6 per plan.

---

## Stage 6 — Stats & Insights (Near)

Changes
- Implemented `GET /api/v1/collisions/near?lat&lon&radius_km[&limit]`:
  - Requires `lat` and `lon` floats; validates `radius_km` (default 1.0, max 10.0) and `limit` (default 100, cap 500).
  - Applies bounding box pruning then Haversine distance; sorts nearest-first and returns minimal fields plus `distance_km`.
  - Reuses `CollisionFilter` so date/weather/quadrant/station filters apply consistently.

Verification
- `python manage.py check` → OK.
- Manual smoke suggested: `/api/v1/collisions/near?lat=51.05&lon=-114.06&radius_km=1.5` and confirm ordering within radius and result caps.

Notes
- Default radius 1.0 km; hard max 10.0 km; default limit 100 with hard cap 500.

---

## Next Steps (Updated)

- Stage 7: Add tests (models, serializers, loaders, endpoints—including stats and near) using `pytest` + factories.
- Stage 8: README quick start, OpenAPI export, seed DB on submission branch, report/video.

---

## Stage 7 — Tests (pytest + pytest-django)

Changes
- Configure pytest for Django: add `pytest.ini` with `DJANGO_SETTINGS_MODULE=calgary_collisions.settings`.
- Add factories in `tests/factories.py` for `WeatherStation`, `WeatherObservation`, `CityDailyWeather`, `Collision`, `Flag`.
- Tests added:
  - `tests/test_models.py`: unique constraints for `Collision.collision_id` and `WeatherObservation (station, date)`.
  - `tests/test_commands.py`: small CSV fixtures written to tmp paths; verify `load_weather` and `load_collisions` create expected rows.
  - `tests/test_api.py`: list/detail collisions, create flag (POST), basic filters, and stats endpoints return expected shapes.
  - `tests/test_near.py`: verify near endpoint constraints (radius, sorted by distance, within radius).

Verification
- Ran `pytest` locally: all tests green.
- Fixed a couple of issues during testing:
  - Monthly stats annotation name conflicted with the `Collision.month` field; changed to aggregate by existing `month` field.
  - Absolute path handling in `load_collisions --csv` adjusted to accept direct file paths in addition to glob patterns.
  - Typo in by-weather stats dict comprehension corrected.

Notes
- Tests avoid large data loads; use factories and tiny CSV fixtures to validate behavior deterministically.
