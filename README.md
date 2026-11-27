# ECO buyurtma boti

Oddiy Telegram buyurtma boti: ro'yxatdan o'tish (telefon), mahsulotlar (Mint, Classic, Premium — 225 000 so'm),
savatcha, joylashuv yuborish, adminga bildirishnoma va buyurtma holatlarini boshqarish.

## Ishga tushirish (kompyuter yoki VPS)

1. Python 3.10+ o'rnatilgan bo'lishi kerak.
2. Papkada terminal oching:

       python -m venv venv
       source venv/bin/activate        # Windows: venv\Scripts\activate
       pip install -r requirements.txt
       python bot.py

3. `.env` faylida token va admin ID turibdi (`BOT_TOKEN`, `ADMIN_IDS`). Bir nechta admin: vergul bilan `111,222`.
4. **Admin botga bir marta /start bosishi shart** — aks holda bot unga bildirishnoma yubora olmaydi.

## Render'da ishga tushirish (Cloud Hosting)

1. Quyidagi 1 bosishli havola orqali Render Blueprint'ni oching:
   https://render.com/deploy?repo=https://github.com/Kamol0303/eco_tabaco/tree/birinchisi
2. `BOT_TOKEN` va `ADMIN_IDS` qiymatlarini kiriting (`WEBAPP_URL` Render'ning `RENDER_EXTERNAL_URL` manzilidan avtomatik olinadi).
3. Qo'lda sozlash uchun Render'da **Web Service** yarating:
   - Branch: `birinchisi`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Health Check Path: `/api/health`
   - Muhit o'zgaruvchilari: `BOT_TOKEN`, `ADMIN_IDS`
4. **Muhim:** Bot Render'da ishlayotganda lokal kompyuterdagi nusxasini to'xtatib qo'ying (aks holda Telegram `TelegramConflictError` beradi).

## VPS'da doimiy ishlashi (systemd)

`/etc/systemd/system/ecobot.service`:

    [Unit]
    Description=ECO Telegram bot
    After=network.target

    [Service]
    WorkingDirectory=/opt/eco_bot
    ExecStart=/opt/eco_bot/venv/bin/python bot.py
    Restart=always
    User=ecobot

    [Install]
    WantedBy=multi-user.target

    sudo systemctl daemon-reload && sudo systemctl enable --now ecobot
    sudo journalctl -u ecobot -f        # loglarni ko'rish

## Admin buyruqlari

- `/admin` — admin panel (yangi buyurtmalar, filtr, statistika, foydalanuvchilar, mahsulotlar)
- `/narx mint 230000` — narxni o'zgartirish (kalitlar: `mint`, `classic`, `premium`)
- `/qidirish Ali` — ism, telefon yoki buyurtma raqami bo'yicha qidirish

## Ma'lumotlar

- Baza: `data/bot.db` (SQLite) — bot qayta ishga tushsa ham saqlanadi
- Zaxira: har 24 soatda `backups/` papkasiga (oxirgi 7 ta)
- Log: `data/bot.log`
