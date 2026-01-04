import pytest
from rest_framework.test import APIClient

from .factories import CollisionFactory, FlagFactory, CityDailyWeatherFactory
from core.models import Flag, WeatherDay


@pytest.mark.django_db
def test_collisions_list_detail_and_flag():
    c1 = CollisionFactory()
    # ensure a different date to avoid CityDailyWeather unique(date) collision
    from datetime import timedelta
    c2 = CollisionFactory(occurred_at=c1.occurred_at + timedelta(days=1))
    c3 = CollisionFactory()

    client = APIClient()

    # List
    resp = client.get("/api/v1/collisions/")
    assert resp.status_code == 200
    assert "results" in resp.json()
    assert len(resp.json()["results"]) >= 3

    # Detail by collision_id
    resp = client.get(f"/api/v1/collisions/{c1.collision_id}/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["collision_id"] == c1.collision_id
    assert "city_weather" in payload

    # Create flag
    resp = client.post(
        "/api/v1/flags/",
        {"collision": c1.collision_id, "note": "hazard present"},
        format="json",
    )
    assert resp.status_code in (200, 201)
    flag_id = resp.json().get("id") if resp.headers.get("content-type","application/json").startswith("application/json") else None
    assert Flag.objects.filter(collision=c1).exists()

    # Retrieve flag
    if flag_id:
        r = client.get(f"/api/v1/flags/{flag_id}/")
        assert r.status_code == 200

        # Update note (PATCH)
        r = client.patch(f"/api/v1/flags/{flag_id}/", {"note": "updated note"}, format="json")
        assert r.status_code in (200, 202)
        # Delete
        r = client.delete(f"/api/v1/flags/{flag_id}/")
        assert r.status_code in (200, 202, 204)


@pytest.mark.django_db
def test_filters_and_stats_endpoints():
    # Create collisions on two different dates and quadrants
    c1 = CollisionFactory(quadrant="NE")
    from datetime import timedelta
    c2 = CollisionFactory(quadrant="SW", occurred_at=c1.occurred_at + timedelta(days=1))
    # City weather for those dates
    CityDailyWeatherFactory(date=c1.date, weather_day_city=WeatherDay.DRY)
    CityDailyWeatherFactory(date=c2.date, weather_day_city=WeatherDay.WET)

    client = APIClient()

    # Filter by quadrant
    r = client.get("/api/v1/collisions/?quadrant=NE")
    assert r.status_code == 200
    results = r.json()["results"]
    assert any(row["quadrant"] == "NE" for row in results)

    # Stats endpoints respond
    for path in [
        "/api/v1/stats/monthly-trend",
        "/api/v1/stats/by-hour",
        "/api/v1/stats/weekday",
        "/api/v1/stats/quadrant-share",
        "/api/v1/stats/top-intersections",
        "/api/v1/stats/by-weather",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "results" in resp.json(), path


@pytest.mark.django_db
def test_invalid_gust_min_param_returns_400():
    # seed one record to ensure list endpoint is active
    CollisionFactory()
    client = APIClient()
    # Non-numeric gust_min should produce a 400 validation error from django-filter
    r = client.get('/api/v1/collisions/?gust_min=not-a-number')
    assert r.status_code == 400


@pytest.mark.django_db
def test_invalid_quadrant_returns_400():
    # seed one record to ensure list endpoint is active
    CollisionFactory()
    client = APIClient()
    r = client.get('/api/v1/collisions/?quadrant=BAD')
    assert r.status_code == 400


@pytest.mark.django_db
def test_page_size_capped_to_200():
    # create more than 200 records
    for _ in range(220):
        CollisionFactory()
    client = APIClient()
    r = client.get('/api/v1/collisions/?page_size=500')
    assert r.status_code == 200
    data = r.json()
    assert 'results' in data
    # capped to 200 by DefaultPagination
    assert len(data['results']) == 200


@pytest.mark.django_db
def test_date_format_validation_and_aliases():
    from datetime import timedelta

    c = CollisionFactory()
    CollisionFactory(occurred_at=c.occurred_at + timedelta(days=2))
    client = APIClient()

    assert client.get('/api/v1/collisions/?from=2024/01/01').status_code == 400
    assert client.get('/api/v1/collisions/?to=20240101').status_code == 400

    r = client.get('/api/v1/collisions/?from=2024-01-01&to=2024-12-31')
    assert r.status_code == 200


@pytest.mark.django_db
def test_stats_by_hour_commute_and_top_limit_clamp():
    from datetime import datetime, timezone

    base = datetime(2024, 3, 10, 8, 0, tzinfo=timezone.utc)
    CollisionFactory(occurred_at=base)
    CollisionFactory(occurred_at=base.replace(hour=17))
    client = APIClient()

    resp = client.get('/api/v1/stats/by-hour?commute=am')
    assert resp.status_code == 200
    hourly = {row['hour']: row['total'] for row in resp.json()['results']}
    assert hourly.get(8)
    assert hourly.get(17, 0) in (0, None)

    resp = client.get('/api/v1/stats/top-intersections?limit=5000')
    assert resp.status_code == 200
    assert resp.json()['limit'] == 100


@pytest.mark.django_db
def test_flag_location_header_and_validation():
    c = CollisionFactory()
    client = APIClient()

    resp = client.post('/api/v1/flags/', {"collision": c.collision_id, "note": "watch"}, format='json')
    assert resp.status_code in (200, 201)
    assert '/api/v1/flags/' in resp.headers.get('Location', '')

    bad = client.post('/api/v1/flags/', {"collision": c.collision_id, "note": ""}, format='json')
    assert bad.status_code == 400
