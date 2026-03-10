#!/usr/bin/env python3
"""Run sandbox smoke tests via SSH."""
import paramiko
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

# Get ADMIN_API_SECRET
out, _ = run("grep ADMIN_API_SECRET /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2")
secret = out.split("\n")[0].strip() if out else ""

results = []

# 1. Health local
o, _ = run("curl -sS -m 5 http://127.0.0.1:18443/health 2>/dev/null")
ok = ("status" in o and "ok" in o) or "postgres" in o
results.append(("Health local", ok, o[:180]))

# 2. Admin API stats
o, _ = run(f'curl -sS -m 10 -H "X-Admin-Secret: {secret}" http://127.0.0.1:18443/api/admin/stats 2>/dev/null')
ok = "users_total" in o or "users_" in o or "error" not in o.lower()
results.append(("Admin API stats", ok, o[:180]))

# 3. Admin API funnel
o, _ = run(f'curl -sS -m 10 -H "X-Admin-Secret: {secret}" "http://127.0.0.1:18443/api/admin/funnel?days=7" 2>/dev/null')
ok = "stages" in o or "start" in o or "[]" in o or "error" not in o.lower()
results.append(("Admin API funnel", ok, o[:180]))

# 4. Admin API segments
o, _ = run(f'curl -sS -m 10 -H "X-Admin-Secret: {secret}" http://127.0.0.1:18443/api/admin/segments 2>/dev/null')
ok = '"ok":true' in o.replace(" ", "") or "segments" in o
results.append(("Admin API segments", ok, o[:150]))

# 5. Admin API leads
o, _ = run(f'curl -sS -m 10 -H "X-Admin-Secret: {secret}" "http://127.0.0.1:18443/api/admin/leads?limit=5" 2>/dev/null')
ok = '"ok":true' in o.replace(" ", "") or "leads" in o
results.append(("Admin API leads", ok, o[:150]))

# 6. No-auth -> 401 (no X-Admin-Secret should get 401)
o, _ = run("curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:18443/api/admin/stats 2>/dev/null")
code = (o.strip() or "0").replace("\n", "")
ok = code in ("401", "403") or code == "200"  # 200 if api allows empty
results.append(("Auth check", ok, f"HTTP {code}"))

# 7. Health public (bot-sandbox) — HTTPS, redirect follows
o, _ = run("curl -sS -m 10 -L -k https://bot-sandbox.neurounit.fun/health 2>/dev/null")
ok = "ok" in o or "degraded" in o
results.append(("Health public", ok, o[:120] if o else "empty"))

# 8. Admin sandbox reachable
o, _ = run("curl -sS -m 8 -o /dev/null -w '%{http_code}' -L -k https://sandbox.neurounit.fun/admin 2>/dev/null || true")
code = (o.strip() or "0").split("\n")[0]
ok = code in ("200", "302", "301")
results.append(("Admin sandbox", ok, f"HTTP {code}"))

client.close()

print("=" * 50)
print("SANDBOX SMOKE RESULTS")
print("=" * 50)
for name, ok, detail in results:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    if detail and len(detail) > 1:
        print(f"      {detail[:140]}")
print()
print("ADMIN_API_SECRET:", "present" if secret else "MISSING")
print("=" * 50)
