#!/usr/bin/env python3
"""
HYDRA BOT — Deploy sandbox via SSH (Python/paramiko)
Usage: python deploy/deploy_sandbox.py
Requires: deploy/.deploy.env with DEPLOY_HOST, DEPLOY_USER, DEPLOY_PASSWORD or DEPLOY_KEY
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_FILE = SCRIPT_DIR / ".deploy.env"

def _remote_script(bot_token_b64: str) -> str:
    return r"""
set -e
SANDBOX_DIR="/opt/hydra_bot_sandbox"
REPO="https://github.com/ivsvivsvivsvivsv-afk/test_bot.git"
BOT_TOKEN_B64=''' + (bot_token_b64 or "") + r'''

if [ -d "$SANDBOX_DIR/.git" ]; then
  cd "$SANDBOX_DIR" && git fetch --all --prune && git reset --hard origin/main
else
  sudo rm -rf "$SANDBOX_DIR" 2>/dev/null || true
  sudo git clone "$REPO" "$SANDBOX_DIR"
fi

cd "$SANDBOX_DIR"
git config --global --add safe.directory "$SANDBOX_DIR"
printf 'TARGET_ENV=sandbox\nTARGET_INSTANCE=hydra-sandbox\n' > .deploy-target

if [ -n "$BOT_TOKEN_B64" ] && [ -f .env ]; then
  BOT_TOKEN=$(echo "$BOT_TOKEN_B64" | base64 -d 2>/dev/null || true)
  if [ -n "$BOT_TOKEN" ]; then
    sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=$BOT_TOKEN|" .env
  fi
fi

# Install systemd and nginx if not yet done
if [ ! -f /etc/systemd/system/hydra-bot-sandbox.service ]; then
  sudo cp "$SANDBOX_DIR/deploy/hydra-bot-sandbox.service" /etc/systemd/system/
  sudo cp "$SANDBOX_DIR/deploy/hydra-worker-sandbox.service" /etc/systemd/system/
  sudo cp "$SANDBOX_DIR/deploy/nginx.sandbox.conf" /etc/nginx/sites-available/hydra-bot-sandbox
  sudo ln -sf /etc/nginx/sites-available/hydra-bot-sandbox /etc/nginx/sites-enabled/
  sudo chown -R www-data:www-data "$SANDBOX_DIR"
  sudo systemctl daemon-reload
  sudo systemctl enable hydra-bot-sandbox hydra-worker-sandbox
  if [ -f /etc/letsencrypt/live/bot-sandbox.neurounit.fun/fullchain.pem ]; then
    sudo nginx -t && sudo systemctl reload nginx
  else
    echo "SSL cert for bot-sandbox.neurounit.fun not found. Run: certbot --nginx -d bot-sandbox.neurounit.fun"
  fi
fi

if [ -f .env ]; then
  echo "sandbox:hydra-sandbox" | sudo bash deploy/guarded_deploy.sh --env sandbox --project-dir "$SANDBOX_DIR"
else
  sudo bash "$SANDBOX_DIR/deploy/setup_sandbox.sh"
fi
echo "[DONE] Sandbox deploy finished"
"""


def load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        print("[FAIL] Create deploy/.deploy.env from .deploy.env.example")
        print("  Add DEPLOY_HOST, DEPLOY_USER, DEPLOY_PASSWORD (or DEPLOY_KEY)")
        sys.exit(1)

    env: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> None:
    try:
        import paramiko
    except ImportError:
        print("[FAIL] Install paramiko: pip install paramiko")
        sys.exit(1)

    env = load_env()
    host = env.get("DEPLOY_HOST")
    user = env.get("DEPLOY_USER")
    password = env.get("DEPLOY_PASSWORD")
    key_path = env.get("DEPLOY_KEY")

    if not host or not user:
        print("[FAIL] DEPLOY_HOST and DEPLOY_USER required in .deploy.env")
        sys.exit(1)

    if not password and not (key_path and Path(key_path).expanduser().exists()):
        print("[FAIL] Add DEPLOY_PASSWORD or DEPLOY_KEY (path to private key) in .deploy.env")
        sys.exit(1)

    bot_token = env.get("SANDBOX_BOT_TOKEN", "").strip()
    token_b64 = base64.b64encode(bot_token.encode()).decode() if bot_token else ""

    print(f"[STEP] Connecting to {user}@{host}...")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_path:
            key_path = Path(key_path).expanduser()
            client.connect(host, username=user, key_filename=str(key_path), timeout=15)
        else:
            client.connect(host, username=user, password=password, timeout=15)

        script = _remote_script(token_b64)
        stdin, stdout, stderr = client.exec_command(script, get_pty=True)
        for line in stdout:
            text = line.rstrip()
            try:
                print(text)
            except UnicodeEncodeError:
                sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        err = stderr.read().decode()
        if err:
            print(err, file=sys.stderr)
        code = stdout.channel.recv_exit_status()
        if code != 0:
            sys.exit(code)
        print("\n[PASS] Sandbox deploy completed")
    finally:
        client.close()


if __name__ == "__main__":
    main()
