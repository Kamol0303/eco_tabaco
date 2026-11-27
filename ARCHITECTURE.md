# ECO Telegram Bot & Mini App Platformasi
## Do'kon va Yetkazib Berish Biznesi uchun To'liq Avtomatlashtirilgan Platforma

Ushbu platforma — mijozlar uchun alohida ilova yuklab olishni talab qilmaydigan, to'g'ridan-to'g'ri Telegram messenjeri ichida ishlaydigan zamonaviy elektron do'kon va buyurtmalarni boshqarish tizimidir (Mini App + Bot + CRM).

---

## 1. 🎯 Asosiy Maqsadi
* **Mijoz uchun:** Alohida dastur o'rnatmasdan Telegram ichida tez, qulay va xarita orqali manzil tanlab buyurtma berish.
* **Biznes egasi (Admin) uchun:** Cho'ntakdagi to'liq boshqaruv (CRM) tizimi: konveyer statuslari, avtomatik SMS-bildirishnomalar, moliya va savdo statistikasi hamda mijozlar bazasi.

---

## 2. 🛠 Texnik Loyiha Tuzilishi va Fayllar Konsepsiyasi

Loyiha **Micro-services / Monolith Hybrid** uslubida yozilgan bo'lib, Telegram bot va WebApp serveri yagona asinxron siklda (`asyncio`) bir-biri bilan uzviy bog'langan.

```text
eco_bot/
├── .env                # Maxfiy konfiguratsiyalar (Token, Admin ID, WebApp URL)
├── config.py           # Loyiha sozlamalari va doimiylar
├── db.py               # SQLite ma'lumotlar bazasi va CRUD metodlar
├── bot.py              # Asosiy Telegram Bot (aiogram 3)
├── webapp_server.py    # Asinxron REST API server (aiohttp)
├── tunnel.log          # Cloudflare HTTPS tunnel loglari
└── webapp/             # Telegram Mini App (Frontend)
    ├── index.html      # SPA (Single Page Application) HTML strukturasi
    ├── styles.css      # Dark-Gold premium UI/UX dizayn tizimi
    └── app.js          # Brauzer biznes mantiqi va API bilan aloqa
```

### Fayllar vazifasi:
1. **`config.py` va `.env` — Konfiguratsiya moduli:**
   * `BOT_TOKEN`: Telegram @BotFather bergan maxfiy token.
   * `ADMIN_IDS`: Adminlarning Telegram ID raqamlari to'plami (`set`).
   * `WEBAPP_URL`: Cloudflare HTTPS havolasi (Telegram WebApp talabi).
   * `WEBAPP_PORT` va `WEBAPP_HOST`: Mini App lokal porti (`8080`) va hosti (`0.0.0.0`).
   * `DB_PATH`, `BACKUP_DIR`: Ma'lumotlar bazasi va avtomatik zaxira nusxalar yo'li.

2. **`db.py` — Ma'lumotlar bazasi (SQLite):**
   * `users`: Telegram ID, ism, telefon raqam, 21+ yosh tasdiqi, ro'yxatdan o'tgan sana.
   * `products`: Nomi, kaliti (`mint`, `classic`, `premium`), ta'rifi, narxi, rasmi, faollik holati.
   * `orders`: ID, user_id, koordinatalar (`lat`/`lon`), jami summa, status, yaratilgan vaqt.
   * `order_items`: Buyurtma tarkibidagi tovarlar, soni va narxi.
   * `cart`: Mijozlarning xotiradagi savatchasi (bot yoki brauzer yopilsa ham saqlanadi).
   * Metodlar: `create_order()`, `set_status()`, `stats()`, `seed_products()`, `backup()`.

3. **`webapp_server.py` — Backend REST API Server (`aiohttp`):**
   * Telegram `initData` imzosini HMAC-SHA256 orqali `BOT_TOKEN` bilan xavfsiz tekshiradi.
   * API: `/api/bootstrap`, `/api/cart`, `/api/orders`, `/api/age-confirm`, `/api/register`.
   * Admin API: `/api/admin/overview`, `/api/admin/orders/{id}/status`, `/api/admin/products/{id}/price`, `/api/admin/products/{id}/toggle`.

4. **`webapp/` — Telegram Mini App (Frontend):**
   * **`index.html`:** SPA strukturasi, OpenStreetMap + Leaflet xaritasi, mahsulotlar modali va 21+ yosh oynasi.
   * **`styles.css`:** Dark-Gold (#0b0e0c fon, #e6b82e oltin) hashamatli mavzu, mobil moslashuvchanlik.
   * **`app.js`:** Reaktiv holat boshqaruvi, `− 0 +` stepperni dinamik boshqarish, GPS geolokatsiya va rolga asoslangan interfeys.

5. **`bot.py` — Telegram Bot (`aiogram 3`):**
   * `/start` menyusi va xush kelibsiz xabari tagida to'g'ridan-to'g'ri `[ 🛍 Mini App do'konini ochish ]` tugmasi.
   * Pastki chap burchakdagi doimiy `🛍 Do'kon` menyu tugmasi (`MenuButtonWebApp`).
   * `send_order_status_notification()`: Admin buyurtma holatini o'zgartirishi bilan xaridorga buyurtma tarkibi, summasi va do'kon tugmasi bilan avtomatik xabar yuborish.
   * 24 soatlik avtomatik zaxiralash sikli (`backup_loop`).

---

## 3. 🔄 Tizimning To'liq Ishlash Sikli (Data Flow)

```text
[Xaridor] ──> Telegram'da «🛍 Do'kon» tugmasini bosadi
     │
     ▼
[Telegram Mini App] ──> HMAC-SHA256 bilan autentifikatsiya qilinadi
     │
     ├──> Mahsulotlarni «− 0 +» orqali savatchaga qo'shadi
     ├──> Xaritada manzilni belgilaydi va «Tasdiqlash» bosadi
     │
     ▼
[webapp_server.py] ──> db.py orqali tranzaksiyada buyurtma yaratadi
     │
     ├──> Barcha Adminlarga Telegram'da: "🆕 YANGI BUYURTMA №X" xabari + GPS lokatsiya boradi
     │
     ▼
[Admin] ──> Mini App yoki Bot orqali buyurtmani «Qabul qilindi» / «Yetkazilmoqda» holatiga o'tkazadi
     │
     ▼
[bot.py] ──> Xaridorga avtomatik SMS: "✅ Buyurtmangiz №X qabul qilindi" (tarkibi va summasi bilan)
```

---

## 4. 🚀 Ishga Tushirish

1. **Virtual muhitni faollashtirish va paketlarni o'rnatish:**
   ```powershell
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Lokal server va Botni yurgizish:**
   ```powershell
   python bot.py
   ```

3. **HTTPS tunnel orqali Telegram Mini App'ni ulash:**
   ```powershell
   .\cloudflared.exe tunnel --url http://127.0.0.1:8080
   ```
   Hosil bo'lgan `https://xxx.trycloudflare.com` manzilini `.env` dagi `WEBAPP_URL` ga yozing.
