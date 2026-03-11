#!/usr/bin/env python3
"""Check bot-sandbox URL accessibility from server and externally."""
import paramiko
import urllib.request
from pathlib import Path

env = {}
for line in Path(__file__).parent.joinpath(".deploy.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        env[k] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(env["DEPLOY_HOST"], username=env["DEPLOY_USER"], password=env["DEPLOY_PASSWORD"])

def run(cmd):
    _, o, e = client.exec_command(cmd)
    return o.read().decode(), e.read().decode()

secret_out, _ = run("grep ADMIN_API_SECRET /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2")
secret = secret_out.split("\n")[0].strip() if secret_out else ""

print("=== DNS resolve (from server) ===")
o, _ = run("getent hosts bot-sandbox.neurounit.fun 2>/dev/null || host bot-sandbox.neurounit.fun 2>/dev/null || echo NXDOMAIN")
print(f"  bot-sandbox.neurounit.fun -> {o.strip() or 'no result'}")

print("\n=== Service status ===")
o, _ = run("systemctl is-active hydra-bot-sandbox 2>/dev/null; ss -tlnp | grep 18443")
print(o[:200])

print("\n=== Recent logs (last 15 lines) ===")
o, _ = run("journalctl -u hydra-bot-sandbox -n 15 --no-pager 2>/dev/null")
print(o[-800:] if len(o) > 800 else o)

print("\n=== From SERVER (127.0.0.1 - direct) ===")
o, err = run("curl -sS -m 5 http://127.0.0.1:18443/health")
print(f"  127.0.0.1:18443/health -> stdout: {repr(o[:100])} stderr: {repr(err[:50])}")

print("\n=== From SERVER (curl to bot-sandbox.neurounit.fun) ===")
for url in [
    "http://bot-sandbox.neurounit.fun/health",
    "http://bot-sandbox.neurounit.fun/api/admin/stats",
    "https://bot-sandbox.neurounit.fun/health",
]:
    headers = f'-H "X-Admin-Secret: {secret}"' if "admin" in url else ""
    o, _ = run(f'curl -sS -m 8 {headers} "{url}" 2>/dev/null')
    status = "OK" if o and ("status" in o or "users_" in o) else "FAIL"
    print(f"  {url}")
    print(f"    -> {status}: {o[:120] if o else repr(o)}")

print("\n=== Nginx config (which one active) ===")
o, _ = run("readlink -f /etc/nginx/sites-enabled/hydra-bot-sandbox 2>/dev/null; head -20 /etc/nginx/sites-enabled/hydra-bot-sandbox 2>/dev/null")
print(o[:500])

print("\n=== BOT_API_URL for landing ===")
print("  Sandbox: BOT_API_URL=http://bot-sandbox.neurounit.fun  (if HTTPS fails, try HTTP)")
print("  Or: BOT_API_URL=https://bot-sandbox.neurounit.fun (needs SSL cert)")

client.close()
