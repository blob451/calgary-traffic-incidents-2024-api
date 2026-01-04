import pytest
from tests.factories import CollisionFactory


@pytest.mark.django_db
def test_smoke_check_module_import():
    CollisionFactory()
    module = __import__("smoke_check")
    assert module is not None
