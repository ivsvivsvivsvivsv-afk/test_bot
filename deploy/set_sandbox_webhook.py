#!/usr/bin/env python3
"""Set webhook for sandbox bot via SSH + Telegram API."""
import urllib.request
import urllib.parse
import json
from pathlib import Path

env_file = Path(__file__).parent / ".deploy.env"
env = {}
for line in env_file.read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        env[k.strip()] = v.strip()

# SSH to get token and secret
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    env["DEPLOY_HOST"],
    username=env["DEPLOY_USER"],
    password=env["DEPLOY_PASSWORD"],
    timeout=15,
)
_, out, _ = client.exec_command(
    "grep -E '^(BOT_TOKEN|WEBHOOK_SECRET)=' /opt/hydra_bot_sandbox/.env"
)
lines = out.read().decode().strip().split("\n")
token = secret = ""
for line in lines:
    if line.startswith("BOT_TOKEN="):
        token = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("WEBHOOK_SECRET="):
        secret = line.split("=", 1)[1].strip().strip('"').strip("'")
client.close()

if not token:
    print("[FAIL] BOT_TOKEN not found")
    exit(1)

url = "https://bot-sandbox.neurounit.fun/webhook/bot"
params = {"url": url}
if secret:
    params["secret_token"] = secret

req_url = f"https://api.telegram.org/bot{token}/setWebhook?" + urllib.parse.urlencode(params)
req = urllib.request.Request(req_url, method="GET")
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())
print("setWebhook:", json.dumps(data, indent=2, ensure_ascii=False))
if data.get("ok"):
    print("\n[OK] Webhook set:", url)
else:
    print("\n[FAIL]", data.get("description", ""))
