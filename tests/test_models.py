import pytest
from django.db import IntegrityError

from .factories import WeatherStationFactory, WeatherObservationFactory, CollisionFactory
from core.models import WeatherObservation, Collision


def test_weather_observation_unique_station_date(db):
    st = WeatherStationFactory()
    obs1 = WeatherObservationFactory(station=st, date="2024-01-05")
    with pytest.raises(IntegrityError):
        WeatherObservation.objects.create(station=st, date=obs1.date)


def test_collision_unique_id(db):
    c1 = CollisionFactory(collision_id="X123")
    with pytest.raises(IntegrityError):
        Collision.objects.create(
            collision_id="X123",
            occurred_at=c1.occurred_at,
            date=c1.date,
            longitude=c1.longitude,
            latitude=c1.latitude,
        )

