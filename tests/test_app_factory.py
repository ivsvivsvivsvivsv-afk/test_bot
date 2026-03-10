from bot import create_app


def test_create_app_registers_required_routes() -> None:
    app = create_app()
    routes = {(route.method, route.resource.canonical) for route in app.router.routes()}

    assert ("GET", "/") in routes
    assert ("GET", "/health") in routes
    assert ("POST", "/yookassa/webhook") in routes
    assert ("GET", "/api/admin/stats") in routes
    assert ("POST", "/api/admin/broadcast") in routes
    assert ("POST", "/api/webhook/site") in routes


def test_create_app_registers_lifecycle_hooks() -> None:
    app = create_app()

    assert app.on_startup
    assert app.on_shutdown
