import pytest
from django.core.management import call_command as django_call_command
from tests.factories import CollisionFactory
from core.models import Flag


@pytest.mark.django_db
def test_seed_invokes_loaders_and_creates_flag(monkeypatch, tmp_path):
    CollisionFactory()

    invoked = {"load_weather": 0, "load_collisions": 0, "build_city_weather": 0}

    def fake_call_command(name, *args, **kwargs):
        if name in invoked:
            invoked[name] += 1
            return
        return django_call_command(name, *args, **kwargs)

    monkeypatch.setattr("core.management.commands.seed.call_command", fake_call_command)

    django_call_command("seed", "--dir", str(tmp_path), "--skip-migrate")

    assert all(v == 1 for v in invoked.values())
    assert Flag.objects.exists()
