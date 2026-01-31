import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "fimadima13").replace("@", "").strip()
GENERATOR_BOT_URL = os.getenv("GENERATOR_BOT_URL", "https://t.me/video_generator_bot").strip()
