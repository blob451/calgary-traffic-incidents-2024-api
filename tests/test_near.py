import pytest
from rest_framework.test import APIClient

from .factories import CollisionFactory


@pytest.mark.django_db
def test_near_endpoint_within_radius_sorted():
    # Seed a reference point
    lat0, lon0 = 51.045, -114.06
    # Create a near and a far collision
    near = CollisionFactory(latitude=lat0 + 0.005, longitude=lon0 + 0.005)
    far = CollisionFactory(latitude=lat0 + 0.05, longitude=lon0 + 0.05)

    client = APIClient()
    resp = client.get(f"/api/v1/collisions/near?lat={lat0}&lon={lon0}&radius_km=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    # First result should be the nearest
    results = data["results"]
    assert all(r["distance_km"] <= 2.0 for r in results)
    # Ensure sorted ascending
    dists = [r["distance_km"] for r in results]
    assert dists == sorted(dists)

