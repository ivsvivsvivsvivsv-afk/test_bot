import importlib


def test_core_modules_import_cleanly() -> None:
    modules = [
        "bot",
        "worker",
        "db",
        "redis_client",
        "handlers.start",
        "handlers.quest",
        "handlers.contacts",
        "handlers.arena",
        "handlers.upsell",
        "handlers.payment_webhook",
        "services.payment_service",
        "services.followup_service",
        "services.broadcast_service",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
