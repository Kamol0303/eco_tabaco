"""Sozlamalar. Maxfiy ma'lumotlar .env faylidan o'qiladi (kodga yozilmaydi)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
admin_str = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or "8031548575,8907509594"
ADMIN_IDS = {
    int(x) for x in admin_str.replace(" ", "").split(",") if x.isdigit()
}

DB_PATH = BASE_DIR / "data" / "bot.db"
BACKUP_DIR = BASE_DIR / "backups"
LOG_PATH = BASE_DIR / "data" / "bot.log"

DEFAULT_PRICE = 225_000   # so'm (bazada keyin /narx buyrug'i bilan o'zgartiriladi)
MAX_QTY = 50              # bitta mahsulotdan maksimal miqdor

if not BOT_TOKEN:
    # Render yoki hostingda token bo'lmasa xato
    pass