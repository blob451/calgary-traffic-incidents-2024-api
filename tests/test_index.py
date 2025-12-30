import os
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_index_shows_runinfo_and_db_info(monkeypatch):
    monkeypatch.setenv('ASSESSMENT_MODE', '1')
    monkeypatch.setenv('ADMIN_USERNAME', 'grader')
    monkeypatch.setenv('ADMIN_PASSWORD', 'secret')

    client = APIClient()
    r = client.get('/')
    assert r.status_code == 200
    body = r.content.decode('utf-8', errors='ignore')

    # Run info markers
    assert 'OpenAPI JSON' in body

    # DB info marker
    assert 'Database engine' in body

