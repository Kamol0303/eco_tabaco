# ECO PLATFORM — Factory Management & Regional Distribution Ecosystem

ECO — Markaziy tamaki ishlab chiqarish zavodi, 14 ta hududiy dilerlar va iste'molchilarni bog'lovchi yagona professional ERP/CRM platformasi.

---

## 🏛 1. Tizim Arxitekturasi

Tizim uch darajali boshqaruv tamoyiliga asoslangan:

```
FACTORY / SUPERADMIN  --->  REGIONAL DEALERS  --->  CUSTOMERS
(Zavod Boshqaruvi)         (Hududiy Adminlar)      (Telegram Mini App)
```

1. **SUPERADMIN (Zavod):**
   - Yagona asosiy boshqaruvchi (ID: `7082420359`).
   - Mahsulotlar (chakana, ulgurji narx, tannarx).
   - Markaziy zavod ombori va qoldiqlar harakati.
   - 14 ta viloyat bo'yicha tovar taqsimoti (Jo'natmalar / Shipments).
   - Hududiy dilerlarni tayinlash, almashtirish va ularning zavod oldidagi qarzdorligini yuritish.
   - Ulgurji savdo (`wholesale`) va Realizatsiya (`consignment`) hisob modellari.
   - Barcha viloyatlar bo'yicha moliyaviy analitika, yalpi foyda (`gross_profit`), audit va CSV/Excel eksport.

2. **REGIONAL DEALERS (Hududiy Dilerlar):**
   - Har bir viloyatga biriktirilgan faol diler Telegram hisobi.
   - Faqat o'z viloyati bo'yicha mustaqil virtual ombor (`stock`, `reserved`, `sold`).
   - O'z hududiga kelgan jo'natmalarni qabul qilish (kamomad va tafovutlarni qayd etish).
   - Faqat o'z viloyatidagi mijozlar va buyurtmalar bilan ishlash.
   - Boshqa viloyat ma'lumotlariga kirish server darajasida (`403 Forbidden`) bloklangan.

3. **CUSTOMERS (Mijozlar):**
   - Telegram Mini App (Luxury Dark & Gold dizayn, xarita, GPS, `− 0 +` steppers).
   - Ro'yxatdan o'tishda viloyat va tumanini tanlaydi.
   - Buyurtma avtomatik ravishda faqat tegishli viloyat dileriga yo'naltiriladi (boshqa dilerlarga bildirishnoma bormaydi).

---

## 🚀 2. Ishga tushirish

1. Virtual muhitni faollashtirish va bog'liqliklarni o'rnatish:
   ```powershell
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. `.env` faylida sozlamalar:
   ```env
   BOT_TOKEN=9297936319:AAE91YbtccXDUfoLqOfLlZbATUQkpTZz7Zg
   SUPERADMIN_IDS=7082420359
   ADMIN_IDS=7082420359,8907509594
   WEBAPP_URL=https://nick-affect-usc-thought.trycloudflare.com
   ```
3. Bot va API serverni ishga tushirish:
   ```powershell
   python bot.py
   ```

---

## 📊 3. Ma'lumotlar Bazasi Modeli (SQLite)

- `users` — Mijozlar, viloyat (`region_id`), tuman (`district`) va yosh tasdig'i (`age_ok`).
- `regions` — O'zbekistonning 14 ta ma'muriy hududi va ularning tumanlari (JSON).
- `dealers` — Har bir hududga biriktirilgan dilerlar, ularning Telegram ID si, narxlash modeli va faollik holati.
- `factory_inventory` — Zavodning markaziy tovar qoldig'i.
- `dealer_inventory` — Dilerlarning virtual ombori (`stock`, `reserved`, `sold`).
- `inventory_transactions` — Ombor harakatlarining o'zgarmas tarixi (Audit ledger).
- `shipments` & `shipment_items` — Zavoddan dilerlarga tovar jo'natish, tracking raqami, tafovutlar (`discrepancy_qty`).
- `dealer_finances` — Dilerlarning zavod oldidagi qarzdorligi va to'lovlari jurnali.
- `audit_log` — Tizimdagi har bir muhim operatsiya (narx o'zgarishi, to'lov, ombor tuzatish) auditi.

---

## 🔒 4. Xavfsizlik

- **HMAC-SHA256 InitData:** Telegram WebApp orqali kelgan har bir so'rov bot tokeni bilan imzosi tekshirilib, foydalanuvchining roli serverda aniqlanadi.
- **Role-Based Access Control (RBAC):** SuperAdmin, Diler va Xaridor huquqlari server tomonda qat'iy ajratilgan.
- **Audit Logging:** Moliyaviy va ombor operatsiyalarini izsiz o'chirish taqiqlangan, har qanday tuzatish qarshi operatsiya bilan qayd etiladi.
