#!/usr/bin/env python3
"""Fix bot-sandbox.neurounit.fun nginx + SSL so /api/admin/stats returns 200."""
import paramiko
from pathlib import Path

env_file = Path(__file__).parent / ".deploy.env"
env = {}
for line in env_file.read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        env[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    env["DEPLOY_HOST"], username=env["DEPLOY_USER"], password=env["DEPLOY_PASSWORD"]
)


def run(cmd, timeout=20):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return o.read().decode() + e.read().decode()


print("=== 1. Current nginx enabled ===")
print(run("ls -la /etc/nginx/sites-enabled/"))

print("\n=== 2. hydra-bot-sandbox config ===")
print(run("cat /etc/nginx/sites-enabled/hydra-bot-sandbox 2>/dev/null || cat /etc/nginx/sites-available/hydra-bot-sandbox 2>/dev/null"))

print("\n=== 3. SSL cert for bot-sandbox ===")
print(run("ls -la /etc/letsencrypt/live/bot-sandbox.neurounit.fun/ 2>/dev/null || echo 'NO_CERT'"))

print("\n=== 4. DNS resolution ===")
print(run("getent hosts bot-sandbox.neurounit.fun 2>/dev/null || echo 'fail'"))

print("\n=== 5. Local curl to 127.0.0.1:18443 ===")
secret = run("grep ADMIN_API_SECRET /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2").strip()
out = run(f'curl -sS -m 5 -H "X-Admin-Secret: {secret}" http://127.0.0.1:18443/api/admin/stats 2>/dev/null')
print("status:", "ok" in out.lower() if out else "empty")
print("body:", (out or "")[:150])

print("\n=== 6. Curl https bot-sandbox from server ===")
out = run(f'curl -sS -m 8 -w "\\nHTTP:%{{http_code}}" -H "X-Admin-Secret: {secret}" https://bot-sandbox.neurounit.fun/api/admin/stats -k 2>/dev/null')
print(out[:250] if out else "timeout/fail")

client.close()
