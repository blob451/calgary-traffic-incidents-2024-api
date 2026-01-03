import math
import pytest
from rest_framework.test import APIClient
from hypothesis import given, strategies as st

from .factories import CollisionFactory


def _km_to_lat(delta_km: float) -> float:
    return delta_km / 111.32


def _km_to_lon(delta_km: float, lat: float) -> float:
    return delta_km / (111.32 * max(1e-6, abs(math.cos(math.radians(lat)))))


@pytest.mark.django_db
@given(
    lat=st.floats(min_value=50.9, max_value=51.2),
    lon=st.floats(min_value=-114.3, max_value=-113.8),
)
def test_near_property_sorted_and_bounded(lat, lon):
    # Seed some collisions around center
    # Within ~0.6 km radius
    for dk in [0.1, 0.3, 0.5]:
        dlat = _km_to_lat(dk)
        dlon = _km_to_lon(dk, lat)
        CollisionFactory(latitude=lat + dlat, longitude=lon + dlon)

    # A couple farther away (~2.5 km)
    dlat_far = _km_to_lat(2.5)
    dlon_far = _km_to_lon(2.5, lat)
    CollisionFactory(latitude=lat + dlat_far, longitude=lon + dlon_far)
    CollisionFactory(latitude=lat - dlat_far, longitude=lon - dlon_far)

    client = APIClient()
    r = client.get(f"/api/v1/collisions/near?lat={lat}&lon={lon}&radius_km=1.0")
    assert r.status_code == 200
    data = r.json()
    # All distances should be within radius and sorted ascending
    dists = [row["distance_km"] for row in data["results"]]
    assert all(d <= 1.0 for d in dists)
    assert dists == sorted(dists)

