import json
import pytest
from rest_framework.test import APIClient

from .factories import CollisionFactory


@pytest.mark.django_db
def test_openapi_schema_available():
    client = APIClient()
    r = client.get('/api/schema/')
    assert r.status_code == 200
    # Try JSON parse; fall back to checking YAML signature
    try:
        json.loads(r.content)
    except Exception:
        body = r.content.decode('utf-8', errors='ignore')
        assert body.strip().startswith('openapi:') or 'openapi' in body


@pytest.mark.django_db
def test_near_requires_lat_lon_and_valid_ranges():
    client = APIClient()
    # missing lat/lon
    r = client.get('/api/v1/collisions/near')
    assert r.status_code == 400
    # invalid range
    r = client.get('/api/v1/collisions/near?lat=999&lon=0')
    assert r.status_code == 400


@pytest.mark.django_db
def test_date_range_validation_on_list():
    # create one record so list endpoint is active
    CollisionFactory()
    client = APIClient()
    r = client.get('/api/v1/collisions/?from=2024-12-31&to=2024-01-01')
    # invalid order should be 400
    assert r.status_code == 400
