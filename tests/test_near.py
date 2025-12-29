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


@pytest.mark.django_db
def test_near_datetime_format_matches_list():
    # Create a collision at a known location
    c = CollisionFactory(latitude=51.05, longitude=-114.06)
    client = APIClient()

    # Get list representation (uses DRF serializer formatting)
    r_list = client.get("/api/v1/collisions/")
    assert r_list.status_code == 200
    list_item = next((i for i in r_list.json()["results"] if i["collision_id"] == c.collision_id), None)
    assert list_item is not None
    occurred_list = list_item["occurred_at"]

    # Get near representation
    r_near = client.get(f"/api/v1/collisions/near?lat={c.latitude}&lon={c.longitude}&radius_km=0.5&limit=1")
    assert r_near.status_code == 200
    results = r_near.json()["results"]
    assert len(results) >= 1
    occurred_near = results[0]["occurred_at"]

    # Formats should be identical strings (normalized by serializer)
    assert occurred_near == occurred_list
