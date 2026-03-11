#!/usr/bin/env python3
"""
Проверка доступности Bot API для лендинга.
Выводит готовый блок .env для sandbox-лендинга.
"""
import urllib.request
import json
from pathlib import Path

env_file = Path(__file__).parent / ".deploy.env"
env = {}
for line in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        env[k.strip()] = v.strip()

# Get secret via SSH
try:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        env["DEPLOY_HOST"],
        username=env["DEPLOY_USER"],
        password=env["DEPLOY_PASSWORD"],
        timeout=10,
    )
    _, out, _ = client.exec_command(
        "grep '^ADMIN_API_SECRET=' /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2-"
    )
    secret = out.read().decode().strip().strip('"').strip("'")
    client.close()
except Exception as e:
    print(f"[WARN] Could not fetch secret via SSH: {e}")
    secret = ""

BOT_API_URL = "https://bot-sandbox.neurounit.fun"

def test_url(url: str, headers: dict = None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.getcode(), r.read().decode()
    except Exception as e:
        return None, str(e)

print("=" * 60)
print("VERIFY BOT API FOR LANDING (sandbox.neurounit.fun/admin)")
print("=" * 60)

# 1. Health (no auth)
code, body = test_url(f"{BOT_API_URL}/health")
print(f"\n1. GET {BOT_API_URL}/health")
print(f"   -> {code}: {'OK' if code == 200 and body else 'FAIL'}")
if body and len(body) < 150:
    print(f"   Body: {body[:120]}")

# 2. Segments (with auth)
headers = {"X-Admin-Secret": secret} if secret else {}
code, body = test_url(f"{BOT_API_URL}/api/admin/segments", headers=headers)
print(f"\n2. GET {BOT_API_URL}/api/admin/segments (with X-Admin-Secret)")
print(f"   -> {code}: {'OK' if code == 200 and 'segments' in (body or '') else 'FAIL'}")
if code == 401:
    print("   ERROR: 401 Unauthorized - ADMIN_API_SECRET не совпадает!")
elif code is None:
    print(f"   ERROR: {body}")

# 3. Stats
code, body = test_url(f"{BOT_API_URL}/api/admin/stats", headers=headers)
print(f"\n3. GET {BOT_API_URL}/api/admin/stats")
print(f"   -> {code}: {'OK' if code == 200 else 'FAIL'}")

print("\n" + "=" * 60)
print("ДЛЯ .env ЛЕНДИНГА (sandbox):")
print("=" * 60)
print(f"""
BOT_API_URL={BOT_API_URL}
ADMIN_API_SECRET={secret if secret else '<ПУСТО — проверьте SSH в deploy/.deploy.env>'}
""")
print("После изменения .env перезапустите/редеплойте лендинг.")
print("=" * 60)
