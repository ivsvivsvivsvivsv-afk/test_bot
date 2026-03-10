"""One-off: inject BOT_TOKEN into server .env via SSH"""
import base64
import paramiko
from pathlib import Path

env = {}
for line in (Path(__file__).parent / ".deploy.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        env[k] = v.strip()

token = env.get("SANDBOX_BOT_TOKEN", "")
if not token:
    print("No SANDBOX_BOT_TOKEN")
    exit(1)

# Write token to temp file on server, then sed
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(env["DEPLOY_HOST"], username=env["DEPLOY_USER"], password=env["DEPLOY_PASSWORD"])
sftp = c.open_sftp()
with sftp.open("/tmp/btoken.txt", "w") as f:
    f.write(token)
sftp.close()
_, o, e = c.exec_command(
    "cd /opt/hydra_bot_sandbox && "
    "TOK=$(cat /tmp/btoken.txt) && "
    "sed -i 's|^BOT_TOKEN=.*|BOT_TOKEN='\"$TOK\"'|' .env && "
    "rm /tmp/btoken.txt"
)
print(o.read().decode(), e.read().decode())
_, o2, _ = c.exec_command("grep BOT_TOKEN /opt/hydra_bot_sandbox/.env")
print(o2.read().decode())
c.close()
