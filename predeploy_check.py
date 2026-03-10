"""
Pre-deploy verification for Hydra bot.

Usage:
    python predeploy_check.py
    python predeploy_check.py --check-services
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent
REQUIRED_ENV_KEYS = (
    "BOT_TOKEN",
    "WEBHOOK_PATH",
    "WEBHOOK_HOST",
    "WEBHOOK_SECRET",
    "DB_PASSWORD",
    "APP_ENV",
    "APP_INSTANCE",
)


def run_step(title: str, command: Sequence[str]) -> None:
    print(f"\n[STEP] {title}")
    print("       ", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {title}")
    print(f"[OK]   {title}")


def validate_required_env() -> None:
    print("\n[STEP] Validate required env")
    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key, "").strip()]
    if missing:
        values = ", ".join(missing)
        raise RuntimeError(
            "Missing required env variables: "
            f"{values}. Fill .env before predeploy check."
        )
    print("[OK]   Required env variables are present")


def _norm_target_env(value: str) -> str:
    v = value.strip().lower()
    if v in {"prod", "production"}:
        return "production"
    if v in {"sandbox", "staging", "stage"}:
        return "sandbox"
    raise RuntimeError(f"Unsupported target env: {value!r}")


def _load_target_marker() -> dict[str, str]:
    marker_path = ROOT / ".deploy-target"
    if not marker_path.exists():
        return {}

    data: dict[str, str] = {}
    for line in marker_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def validate_env_format(
    strict_prod: bool,
    target_env: str,
    expected_webhook_host: str | None,
) -> None:
    print("\n[STEP] Validate env format")
    token = os.getenv("BOT_TOKEN", "").strip()
    if not re.match(r"^\d{6,15}:[A-Za-z0-9_-]{30,80}$", token):
        raise RuntimeError("BOT_TOKEN has invalid format")

    webhook_host = os.getenv("WEBHOOK_HOST", "").strip()
    if not webhook_host.startswith("https://"):
        raise RuntimeError("WEBHOOK_HOST must start with https://")
    if expected_webhook_host and webhook_host.rstrip("/") != expected_webhook_host.rstrip("/"):
        raise RuntimeError(
            "WEBHOOK_HOST mismatch: "
            f"expected {expected_webhook_host!r}, got {webhook_host!r}"
        )

    webhook_path = os.getenv("WEBHOOK_PATH", "").strip()
    if not webhook_path.startswith("/"):
        raise RuntimeError("WEBHOOK_PATH must start with '/'")

    db_pool_min = int(os.getenv("DB_POOL_MIN", "2"))
    db_pool_max = int(os.getenv("DB_POOL_MAX", "10"))
    if db_pool_min < 1 or db_pool_max < 1 or db_pool_min > db_pool_max:
        raise RuntimeError("Invalid DB_POOL_MIN/DB_POOL_MAX values")
    if db_pool_max > 20:
        print("[WARN] DB_POOL_MAX > 20, double-check PostgreSQL capacity")

    admin_ids = os.getenv("ADMIN_IDS", "").strip()
    if not admin_ids:
        print("[WARN] ADMIN_IDS is empty, admin commands will be unavailable")

    app_env = os.getenv("APP_ENV", "").strip().lower()
    app_instance = os.getenv("APP_INSTANCE", "").strip()
    if app_env != target_env:
        raise RuntimeError(
            f"APP_ENV must be '{target_env}' for target-env check, got {app_env!r}"
        )
    if not app_instance:
        raise RuntimeError("APP_INSTANCE must be set (e.g. hydra-prod / hydra-sandbox)")

    marker = _load_target_marker()
    marker_env = marker.get("TARGET_ENV", "").strip().lower()
    marker_instance = marker.get("TARGET_INSTANCE", "").strip()
    if marker_env and marker_env != target_env:
        raise RuntimeError(
            f".deploy-target TARGET_ENV={marker_env!r} conflicts with --target-env={target_env!r}"
        )
    if marker_instance and marker_instance != app_instance:
        raise RuntimeError(
            f".deploy-target TARGET_INSTANCE={marker_instance!r} conflicts with APP_INSTANCE={app_instance!r}"
        )

    if target_env == "production":
        if any(x in webhook_host.lower() for x in ("sandbox", "staging", "stage")):
            raise RuntimeError("Production target cannot use sandbox/staging WEBHOOK_HOST")
    else:
        if "bot.neurounit.fun" in webhook_host.lower():
            raise RuntimeError(
                "Sandbox target must not use production WEBHOOK_HOST=bot.neurounit.fun"
            )

    if strict_prod:
        if target_env != "production":
            raise RuntimeError("--strict-prod can be used only with --target-env production")
        yookassa_secret = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
        if not yookassa_secret:
            raise RuntimeError("YOOKASSA_SECRET_KEY is required in --strict-prod mode")
        if yookassa_secret.startswith("test_"):
            raise RuntimeError("YOOKASSA_SECRET_KEY must be LIVE key in --strict-prod mode")
        if "CHANGE_ME" in os.getenv("WEBHOOK_SECRET", ""):
            raise RuntimeError("WEBHOOK_SECRET still contains placeholder value")

    print("[OK]   Env format is valid")


def run_smoke_import() -> None:
    print("\n[STEP] Runtime smoke import")
    for module_name in ("config", "bot", "worker", "handlers.payment_webhook"):
        importlib.import_module(module_name)

    from bot import create_app

    app = create_app()
    route_count = len(list(app.router.routes()))
    if route_count < 3:
        raise RuntimeError(f"Unexpected route count: {route_count}")
    print(f"[OK]   Smoke import passed, routes={route_count}")


async def check_external_services() -> None:
    print("\n[STEP] Check PostgreSQL and Redis connectivity")
    from config import DB_DSN, REDIS_URL
    import asyncpg
    from redis.asyncio import Redis

    conn = await asyncpg.connect(dsn=DB_DSN, timeout=3)
    try:
        value = await conn.fetchval("SELECT 1")
        if value != 1:
            raise RuntimeError("PostgreSQL probe returned unexpected value")
    finally:
        await conn.close()

    redis = Redis.from_url(REDIS_URL, decode_responses=False)
    try:
        pong = await redis.ping()
        if pong is not True:
            raise RuntimeError("Redis ping failed")
    finally:
        await redis.aclose()
    print("[OK]   PostgreSQL and Redis are reachable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hydra bot predeploy checker")
    parser.add_argument(
        "--check-services",
        action="store_true",
        help="Check live PostgreSQL and Redis connectivity",
    )
    parser.add_argument(
        "--strict-prod",
        action="store_true",
        help="Enable strict production checks (LIVE keys and placeholders validation)",
    )
    parser.add_argument(
        "--target-env",
        default="production",
        help="Deployment target: production|sandbox (default: production)",
    )
    parser.add_argument(
        "--expected-webhook-host",
        default="",
        help="Optional explicit WEBHOOK_HOST assertion",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        target_env = _norm_target_env(args.target_env)
        expected_webhook_host = args.expected_webhook_host.strip() or None
        validate_required_env()
        validate_env_format(
            strict_prod=args.strict_prod,
            target_env=target_env,
            expected_webhook_host=expected_webhook_host,
        )
        run_step("Dependency sanity check", [sys.executable, "-m", "pip", "check"])
        run_step(
            "Compile project",
            [
                sys.executable,
                "-m",
                "compileall",
                "bot.py",
                "worker.py",
                "handlers",
                "services",
                "middlewares",
                "utils",
                "models",
                "keyboards",
                "config.py",
                "db.py",
                "redis_client.py",
            ],
        )
        run_step("Run tests", [sys.executable, "-m", "pytest", "-q"])
        run_smoke_import()
        if args.check_services:
            asyncio.run(check_external_services())
    except Exception as exc:
        print(f"\n[FAIL] {exc}")
        return 1

    print("\n[PASS] Predeploy checks completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
