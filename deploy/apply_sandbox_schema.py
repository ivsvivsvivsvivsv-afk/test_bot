#!/usr/bin/env python3
"""Apply schema to sandbox DB via SSH."""
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
    env["DEPLOY_HOST"],
    username=env["DEPLOY_USER"],
    password=env["DEPLOY_PASSWORD"],
    timeout=15,
)

# Upload schema
sftp = client.open_sftp()
proj = Path(__file__).resolve().parent.parent
sftp.put(str(proj / "schema.sql"), "/opt/hydra_bot_sandbox/schema.sql")
sftp.close()

# Get DB_PASSWORD from remote .env
_, out, _ = client.exec_command(
    "grep '^DB_PASSWORD=' /opt/hydra_bot_sandbox/.env | cut -d= -f2-"
)
pw = out.read().decode().strip().strip('"').strip("'")

# Apply schema
cmd = (
    f"PGPASSWORD='{pw}' psql -U hydra -d hydra_bot_sandbox -h localhost "
    "-f /opt/hydra_bot_sandbox/schema.sql 2>&1"
)
_, out, err = client.exec_command(cmd, timeout=60)
result = out.read().decode() + err.read().decode()
print(result[:800])
client.close()
