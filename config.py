"""Sozlamalar. Maxfiy ma'lumotlar .env faylidan o'qiladi (kodga yozilmaydi)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
}

DB_PATH = BASE_DIR / "data" / "bot.db"
BACKUP_DIR = BASE_DIR / "backups"
LOG_PATH = BASE_DIR / "data" / "bot.log"
WEBAPP_DIR = BASE_DIR / "webapp"

WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0").strip()
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

DEFAULT_PRICE = 225_000   # so'm (bazada keyin /narx buyrug'i bilan o'zgartiriladi)
MAX_QTY = 50              # bitta mahsulotdan maksimal miqdor

if not BOT_TOKEN:
    raise RuntimeError(".env faylida BOT_TOKEN ko'rsatilmagan")
if not ADMIN_IDS:
    raise RuntimeError(".env faylida ADMIN_IDS ko'rsatilmagan")
