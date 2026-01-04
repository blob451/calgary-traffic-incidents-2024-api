def test_asgi_and_wsgis_callable():
    import calgary_collisions.asgi as asgi
    import calgary_collisions.wsgi as wsgi

    assert callable(asgi.application)
    assert callable(wsgi.application)
