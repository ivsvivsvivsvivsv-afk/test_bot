import os
import sys

import pytest


@pytest.fixture(autouse=True)
def stable_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE12345",
        "WEBHOOK_HOST": "https://example.com",
        "WEBHOOK_SECRET": "test-secret",
        "DB_PASSWORD": "test-password",
        "DB_USER": "hydra",
        "DB_NAME": "hydra_bot",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # Ensure modules depending on config are loaded with test env.
    for module_name in ("config", "bot", "worker"):
        sys.modules.pop(module_name, None)

    yield
