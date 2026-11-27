"""Sozlamalar. Maxfiy ma'lumotlar .env faylidan o'qiladi (kodga yozilmaydi)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
admin_str = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or "7082420359,8907509594,8031548575"
ADMIN_IDS = {
    int(x) for x in admin_str.replace(" ", "").split(",") if x.isdigit()
}

DB_PATH = BASE_DIR / "data" / "bot.db"
BACKUP_DIR = BASE_DIR / "backups"
LOG_PATH = BASE_DIR / "data" / "bot.log"

DEFAULT_PRICE = 225_000   # so'm
MAX_QTY = 50

WEBAPP_DIR = BASE_DIR / "webapp"
WEBAPP_PORT = int(os.getenv("PORT") or os.getenv("WEBAPP_PORT") or 8080)
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://kamol0303.github.io/eco_tabaco/").strip()
