import pytest
from rest_framework.test import APIClient

from .factories import (
    CollisionFactory,
    CityDailyWeatherFactory,
    WeatherObservationFactory,
    WeatherStationFactory,
)
from core.models import WeatherDay


@pytest.mark.django_db
def test_freeze_and_precip_snow_filters_work():
    # Two collisions on different dates
    c1 = CollisionFactory()
    from datetime import timedelta
    c2 = CollisionFactory(occurred_at=c1.occurred_at + timedelta(days=1))

    # City daily weather: c1 date freeze True, rain True; c2 snow True
    CityDailyWeatherFactory(
        date=c1.date, freeze_day_city=True, precip_any=True, snow_any=False, weather_day_city=WeatherDay.WET
    )
    CityDailyWeatherFactory(
        date=c2.date, freeze_day_city=False, precip_any=False, snow_any=True, weather_day_city=WeatherDay.SNOWY
    )

    client = APIClient()

    r = client.get("/api/v1/collisions/?freeze_day_city=true")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c1.collision_id in ids and c2.collision_id not in ids

    r = client.get("/api/v1/collisions/?heavy_rain=true")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c1.collision_id in ids and c2.collision_id not in ids

    r = client.get("/api/v1/collisions/?heavy_snow=true")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c2.collision_id in ids and c1.collision_id not in ids


@pytest.mark.django_db
def test_gust_min_and_station_filters():
    # Create two stations
    st1 = WeatherStationFactory(name="Calgary Intl A", climate_id="AB3031092")
    st2 = WeatherStationFactory(name="University", climate_id="3032000")

    # Collisions bound to these stations
    c1 = CollisionFactory(nearest_station=st1)
    c2 = CollisionFactory(nearest_station=st2)

    # Observations for those stations/dates
    WeatherObservationFactory(station=st1, date=c1.date, gust_kmh=65)
    WeatherObservationFactory(station=st2, date=c2.date, gust_kmh=20)

    client = APIClient()

    # gust_min should include c1 only
    r = client.get("/api/v1/collisions/?gust_min=50")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c1.collision_id in ids and c2.collision_id not in ids

    # station by id
    r = client.get(f"/api/v1/collisions/?station={st1.id}")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c1.collision_id in ids and c2.collision_id not in ids

    # station by climate_id (case insensitive, non-digit to avoid ID branch)
    r = client.get("/api/v1/collisions/?station=ab3031092")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c1.collision_id in ids and c2.collision_id not in ids

    # station by name substring
    r = client.get("/api/v1/collisions/?station=university")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert c2.collision_id in ids and c1.collision_id not in ids


@pytest.mark.django_db
def test_weather_day_city_aliases_and_invalid_inputs():
    from datetime import timedelta

    c1 = CollisionFactory()
    c2 = CollisionFactory(occurred_at=c1.occurred_at + timedelta(days=1))

    CityDailyWeatherFactory(date=c1.date, weather_day_city=WeatherDay.DRY, freeze_day_city=True)
    CityDailyWeatherFactory(date=c2.date, weather_day_city=WeatherDay.SNOWY, freeze_day_city=False)

    client = APIClient()

    r = client.get("/api/v1/collisions/?weather_day_city=snowy")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c2.collision_id}

    r = client.get("/api/v1/collisions/?weather_day_city=DRY")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c1.collision_id}

    # Unknown weather_day should not filter anything
    r = client.get("/api/v1/collisions/?weather_day_city=stormy")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c1.collision_id, c2.collision_id}

    # freeze_day accepts truthy strings and caps to boolean filter
    r = client.get("/api/v1/collisions/?freeze_day_city=Yes")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c1.collision_id}

    r = client.get("/api/v1/collisions/?freeze_day_city=no")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c2.collision_id}

    # invalid boolean should leave results unchanged
    r = client.get("/api/v1/collisions/?freeze_day_city=maybe")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c1.collision_id, c2.collision_id}

    # station empty string should not filter
    r = client.get("/api/v1/collisions/?station=")
    assert r.status_code == 200
    ids = {row["collision_id"] for row in r.json()["results"]}
    assert ids == {c1.collision_id, c2.collision_id}

