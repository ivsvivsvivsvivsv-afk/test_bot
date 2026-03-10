import os
import random

from locust import HttpUser, between, task


WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


class TelegramWebhookUser(HttpUser):
    wait_time = between(0.01, 0.2)

    @task(3)
    def send_start_command(self) -> None:
        user_id = random.randint(1_000_000, 9_999_999)
        update_id = random.randint(1_000_000_000, 2_000_000_000)
        payload = {
            "update_id": update_id,
            "message": {
                "message_id": random.randint(1, 1_000_000),
                "date": 1700000000,
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": "Load",
                    "username": f"load_{user_id}",
                    "language_code": "ru",
                },
                "chat": {
                    "id": user_id,
                    "type": "private",
                },
                "text": "/start",
            },
        }
        headers = {"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}
        self.client.post("/webhook/bot", json=payload, headers=headers, name="POST /webhook/bot /start")

    @task(1)
    def send_health_probe(self) -> None:
        self.client.get("/health", name="GET /health")
