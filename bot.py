"""ECO buyurtma boti (aiogram 3). Ishga tushirish: python bot.py"""
import asyncio
import html
import logging
import os
from datetime import datetime

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    ErrorEvent,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import ADMIN_IDS, BACKUP_DIR, BASE_DIR, BOT_TOKEN, DB_PATH, DEFAULT_PRICE, LOG_PATH, MAX_QTY
from db import Database, now_str

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("eco_bot")

db = Database(DB_PATH)
db.seed_products(
    [
        (
            "mint",
            "ECO Mint",
            "Yalpiz ta'mli fermentlangan tamaki. Original brend, klassik retsept.",
            DEFAULT_PRICE,
            "images/mint.jpg",
        ),
        (
            "classic",
            "ECO Classic",
            "Klassik ta'mli fermentlangan tamaki. Original brend, klassik retsept.",
            DEFAULT_PRICE,
            "images/classic.jpg",
        ),
        (
            "premium",
            "ECO Premium",
            "Premium sifatli innovatsion tamaki. Original brend, klassik retsept.",
            DEFAULT_PRICE,
            "images/premium.jpg",
        ),
    ]
)

# ====================== Matnlar va holatlar ======================
BTN_CATALOG = "🛍 Mahsulotlar"
BTN_CART = "🛒 Savatcha"
BTN_ORDERS = "📦 Buyurtmalarim"
BTN_PROFILE = "👤 Ma'lumotlarim"
BTN_ADMIN = "🔧 Admin panel"
BTN_CANCEL = "❌ Bekor qilish"

A_NEW = "📋 Yangi buyurtmalar"
A_ORDERS = "📦 Barcha buyurtmalar"
A_STATS = "📊 Statistika"
A_USERS = "👥 Foydalanuvchilar"
A_PRODUCTS = "🛠 Mahsulotlar"
A_BACK = "⬅️ Asosiy menyu"

STATUSES = {
    "new": "Yangi",
    "accepted": "Qabul qilindi",
    "preparing": "Tayyorlanmoqda",
    "delivering": "Yetkazilmoqda",
    "done": "Yakunlandi",
    "cancelled": "Bekor qilindi",
}
STATUS_EMOJI = {
    "new": "🆕",
    "accepted": "✅",
    "preparing": "👨‍🍳",
    "delivering": "🚚",
    "done": "🎉",
    "cancelled": "❌",
}
FLOW = ["accepted", "preparing", "delivering", "done", "cancelled"]  # admin tugmalari
FINAL = {"done", "cancelled"}  # yakunlangan holatlarni o'zgartirib bo'lmaydi

USER_STATUS_MSG = {
    "accepted": "✅ Buyurtmangiz <b>№{oid}</b> qabul qilindi.",
    "preparing": "👨‍🍳 Buyurtmangiz <b>№{oid}</b> tayyorlanmoqda.",
    "delivering": "🚚 Buyurtmangiz <b>№{oid}</b> yetkazilmoqda.",
    "done": "🎉 Buyurtmangiz <b>№{oid}</b> yakunlandi. Xaridingiz uchun rahmat!",
    "cancelled": "❌ Buyurtmangiz <b>№{oid}</b> bekor qilindi. Savollar bo'lsa, biz bilan bog'laning.",
}


class Order(StatesGroup):
    location = State()
    confirm = State()


# ====================== Yordamchi funksiyalar ======================
def esc(s) -> str:
    return html.escape(str(s or ""))


def money(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def fmt_dt(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return s or "-"


def status_label(code: str) -> str:
    return f"{STATUS_EMOJI.get(code, '')} {STATUSES.get(code, code)}"


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def chunk(items: list, n: int = 2) -> list[list]:
    return [items[i : i + n] for i in range(0, len(items), n)]


async def safe_edit_text(msg: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def safe_edit_markup(msg: Message, kb: InlineKeyboardMarkup) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ====================== Klaviaturalar ======================
def main_menu(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)],
        [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_PROFILE)],
    ]
    if admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=A_NEW), KeyboardButton(text=A_ORDERS)],
            [KeyboardButton(text=A_STATS), KeyboardButton(text=A_USERS)],
            [KeyboardButton(text=A_PRODUCTS), KeyboardButton(text=A_BACK)],
        ],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def product_kb(pid: int, qty: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("➖", f"pd:{pid}"), btn(f"🛒 {qty} ta", "noop"), btn("➕", f"pi:{pid}")],
            [btn("🧺 Savatchani ko'rish", "cart")],
        ]
    )


def render_cart(uid: int, edit: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    items = db.cart_items(uid)
    if not items:
        return (
            "🛒 Savatchangiz hozircha bo'sh.",
            InlineKeyboardMarkup(inline_keyboard=[[btn("🛍 Mahsulotlarni ko'rish", "catalog")]]),
        )
    lines = ["🛒 <b>Savatcha</b>\n"]
    total = 0
    for i, it in enumerate(items, 1):
        s = it["price"] * it["qty"]
        total += s
        lines.append(
            f"{i}. <b>{esc(it['name'])}</b>\n    {it['qty']} × {money(it['price'])} = {money(s)} so'm"
        )
    lines.append(f"\n💰 <b>Jami: {money(total)} so'm</b>")
    if edit:
        rows = []
        for it in items:
            pid = it["product_id"]
            short = it["name"].replace("ECO ", "")
            rows.append(
                [
                    btn("➖", f"cd:{pid}"),
                    btn(f"{short} · {it['qty']}", "noop"),
                    btn("➕", f"ci:{pid}"),
                    btn("❌", f"cx:{pid}"),
                ]
            )
        rows.append([btn("✅ Tahrirlashni yakunlash", "cart")])
    else:
        rows = [
            [btn("✅ Buyurtma berish", "checkout")],
            [btn("✏️ Tahrirlash", "cart_edit"), btn("🗑 Tozalash", "cart_clear")],
        ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


# ====================== Buyurtma kartasi (admin) ======================
def order_text(o, items) -> str:
    header = "🆕 <b>YANGI BUYURTMA</b>" if o["status"] == "new" else "📦 <b>BUYURTMA</b>"
    lines = [
        header,
        "",
        f"🔢 Buyurtma raqami: <b>№{o['id']}</b>",
        f"👤 Mijoz: <a href=\"tg://user?id={o['user_id']}\">{esc(o['user_name'])}</a>",
        f"🆔 Telegram ID: <code>{o['user_id']}</code>",
        f"📞 Telefon: {esc(o['phone'])}",
        f"🕒 Sana: {fmt_dt(o['created_at'])}",
        f"📊 Holat: <b>{status_label(o['status'])}</b>",
        "",
        "🧾 <b>Buyurtma tarkibi:</b>",
    ]
    for it in items:
        lines.append(
            f"• {esc(it['product_name'])} — {it['qty']} × {money(it['price'])} "
            f"= {money(it['qty'] * it['price'])} so'm"
        )
    lines += [
        "",
        f"💰 <b>Jami: {money(o['total'])} so'm</b>",
        f"📍 Koordinatalar: <code>{o['lat']:.6f}, {o['lon']:.6f}</code>",
    ]
    return "\n".join(lines)


def admin_order_kb(o) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🗺 Xaritada ochish",
                url=f"https://www.google.com/maps?q={o['lat']},{o['lon']}",
            )
        ]
    ]
    if o["status"] not in FINAL:
        buttons = [
            btn(f"{STATUS_EMOJI[c]} {STATUSES[c]}", f"st:{o['id']}:{c}")
            for c in FLOW
            if c != o["status"]
        ]
        rows += chunk(buttons, 2)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_order_card(bot: Bot, chat_id: int, oid: int) -> None:
    o = db.get_order(oid)
    if not o:
        return
    m = await bot.send_message(chat_id, order_text(o, db.order_items(oid)), reply_markup=admin_order_kb(o))
    await bot.send_location(chat_id, o["lat"], o["lon"], reply_to_message_id=m.message_id)


async def notify_admins(bot: Bot, oid: int) -> None:
    for aid in ADMIN_IDS:
        try:
            await send_order_card(bot, aid, oid)
        except Exception:
            log.exception("Adminga (%s) bildirishnoma yuborilmadi. Admin botga /start bosganmi?", aid)


# ====================== Mahsulotlar katalogi ======================
async def send_product(bot: Bot, chat_id: int, uid: int, p) -> None:
    caption = (
        f"<b>{esc(p['name'])}</b>\n{esc(p['description'])}\n\n"
        f"💰 Narxi: <b>{money(p['price'])} so'm</b>"
    )
    kb = product_kb(p["id"], db.cart_qty(uid, p["id"]))
    if p["file_id"]:
        try:
            await bot.send_photo(chat_id, p["file_id"], caption=caption, reply_markup=kb)
            return
        except TelegramBadRequest:
            log.warning("file_id yaroqsiz (%s), rasm qayta yuklanadi", p["key"])
    path = BASE_DIR / (p["image"] or "")
    if p["image"] and path.exists():
        msg = await bot.send_photo(chat_id, FSInputFile(path), caption=caption, reply_markup=kb)
        db.set_file_id(p["id"], msg.photo[-1].file_id)
    else:
        await bot.send_message(chat_id, caption, reply_markup=kb)


async def send_catalog(bot: Bot, chat_id: int, uid: int) -> None:
    products = db.products()
    if not products:
        await bot.send_message(chat_id, "Hozircha mahsulotlar mavjud emas.")
        return
    await bot.send_message(chat_id, "🛍 <b>Mahsulotlar</b>\nKerakli miqdorni ➕ / ➖ tugmalari bilan tanlang:")
    for p in products:
        await send_product(bot, chat_id, uid, p)


# ====================== Routerlar ======================
reg = Router()    # ro'yxatdan o'tish (hamma uchun)
admin = Router()  # faqat adminlar
user = Router()   # faqat ro'yxatdan o'tgan foydalanuvchilar

admin.message.filter(F.from_user.id.in_(ADMIN_IDS))
admin.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class RegisteredOnly(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and not db.is_registered(u.id):
            text = "Avval ro'yxatdan o'ting: /start buyrug'ini bosing."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
            return None
        return await handler(event, data)


user.message.middleware(RegisteredOnly())
user.callback_query.middleware(RegisteredOnly())


# ---------------------- Ro'yxatdan o'tish ----------------------
async def ask_phone(m: Message) -> None:
    await m.answer(
        "📱 Ro'yxatdan o'tish uchun pastdagi tugma orqali telefon raqamingizni yuboring.\n\n"
        "ℹ️ Telefon raqamingiz, Telegram ID va ismingiz buyurtmalaringizni qabul qilish va "
        "siz bilan bog'lanish uchun saqlanadi. Ma'lumotlar uchinchi shaxslarga berilmaydi.",
        reply_markup=phone_kb(),
    )


@reg.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    u = m.from_user
    db.touch_user(u.id, u.full_name)
    row = db.get_user(u.id)
    if row["phone"]:
        await m.answer(
            f"Qaytganingiz bilan, <b>{esc(row['name'])}</b>! 👋\nKerakli bo'limni tanlang.",
            reply_markup=main_menu(is_admin(u.id)),
        )
        return
    await m.answer(
        f"Assalomu alaykum, <b>{esc(u.full_name)}</b>! 👋\n<b>ECO</b> buyurtma botiga xush kelibsiz.",
        reply_markup=ReplyKeyboardRemove(),
    )
    if row["age_ok"]:
        await ask_phone(m)
        return
    await m.answer(
        "Bu bot tamaki mahsulotlarini sotadi. Davom etish uchun 18 yoshdan oshganingizni tasdiqlang.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[btn("✅ Ha, 18 yoshdaman", "age_yes"), btn("❌ Yo'q", "age_no")]]
        ),
    )


@reg.callback_query(F.data == "age_yes")
async def age_yes(cb: CallbackQuery):
    db.touch_user(cb.from_user.id, cb.from_user.full_name)
    db.set_age_ok(cb.from_user.id)
    await safe_edit_text(cb.message, "✅ Yoshingiz tasdiqlandi.")
    await ask_phone(cb.message)
    await cb.answer()


@reg.callback_query(F.data == "age_no")
async def age_no(cb: CallbackQuery):
    await safe_edit_text(cb.message, "Kechirasiz, bu bot faqat 18 yoshdan oshganlar uchun.")
    await cb.answer()


@reg.message(F.contact)
async def on_contact(m: Message):
    u, c = m.from_user, m.contact
    row = db.get_user(u.id)
    if not row or not row["age_ok"]:
        await m.answer("Avval /start buyrug'ini bosing va yoshingizni tasdiqlang.")
        return
    if c.user_id != u.id:
        await m.answer(
            "❌ Faqat o'zingizning telefon raqamingizni yuborishingiz mumkin. "
            "Pastdagi tugmani bosing.",
            reply_markup=phone_kb(),
        )
        return
    phone = c.phone_number if c.phone_number.startswith("+") else "+" + c.phone_number
    db.register(u.id, u.full_name, phone)
    log.info("Yangi foydalanuvchi ro'yxatdan o'tdi: %s", u.id)
    await m.answer(
        "✅ Ro'yxatdan o'tdingiz! Endi mahsulotlarni tanlashingiz mumkin.",
        reply_markup=main_menu(is_admin(u.id)),
    )


# ---------------------- Admin ----------------------
def orders_list_view(orders, title: str, back: bool = False):
    if not orders:
        text = f"{title}\n\nBuyurtmalar topilmadi."
        rows = []
    else:
        text = f"{title}\nBatafsil ko'rish uchun buyurtmani tanlang:"
        rows = [
            [
                btn(
                    f"№{o['id']} · {o['user_name'][:16]} · {money(o['total'])} · "
                    f"{STATUS_EMOJI.get(o['status'], '')}",
                    f"v:{o['id']}",
                )
            ]
            for o in orders
        ]
    if back:
        rows.append([btn("⬅️ Orqaga", "fb")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def filter_menu() -> tuple[str, InlineKeyboardMarkup]:
    buttons = [btn("📦 Hammasi", "f:all")] + [
        btn(status_label(c), f"f:{c}") for c in STATUSES
    ]
    return "📦 <b>Buyurtmalar</b>\nQaysi buyurtmalarni ko'rmoqchisiz?", InlineKeyboardMarkup(
        inline_keyboard=chunk(buttons, 2)
    )


def products_view() -> tuple[str, InlineKeyboardMarkup]:
    products = db.products(active_only=False)
    lines = ["🛠 <b>Mahsulotlar</b>\n"]
    rows = []
    for p in products:
        state = "🟢 Faol" if p["active"] else "🔴 O'chirilgan"
        lines.append(f"• <b>{esc(p['name'])}</b> — {money(p['price'])} so'm — {state}  (<code>{p['key']}</code>)")
        action = "🔴 O'chirish" if p["active"] else "🟢 Yoqish"
        rows.append([btn(f"{action}: {p['name']}", f"tg:{p['id']}")])
    lines.append("\nNarxni o'zgartirish: <code>/narx mint 230000</code>")
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@admin.message(Command("admin"))
@admin.message(F.text == BTN_ADMIN)
async def a_panel(m: Message):
    await m.answer(
        "🔧 <b>Admin panel</b>\nKerakli bo'limni tanlang.\n"
        "Qidirish: <code>/qidirish ism yoki telefon yoki raqam</code>",
        reply_markup=admin_menu(),
    )


@admin.message(F.text == A_BACK)
async def a_back(m: Message):
    await m.answer("Asosiy menyu.", reply_markup=main_menu(True))


@admin.message(F.text == A_NEW)
async def a_new(m: Message, bot: Bot):
    orders = db.list_orders(status="new", limit=10)
    if not orders:
        await m.answer("Yangi buyurtmalar yo'q. ✅")
        return
    await m.answer(f"🆕 Yangi buyurtmalar: {len(orders)} ta (oxirgisi birinchi)")
    for o in orders:
        await send_order_card(bot, m.chat.id, o["id"])


@admin.message(F.text == A_ORDERS)
async def a_orders(m: Message):
    text, kb = filter_menu()
    await m.answer(text, reply_markup=kb)


@admin.callback_query(F.data == "fb")
async def a_filter_back(cb: CallbackQuery):
    text, kb = filter_menu()
    await safe_edit_text(cb.message, text, kb)
    await cb.answer()


@admin.callback_query(F.data.startswith("f:"))
async def a_filter(cb: CallbackQuery):
    code = cb.data.split(":", 1)[1]
    if code != "all" and code not in STATUSES:
        await cb.answer()
        return
    orders = db.list_orders(status=None if code == "all" else code, limit=10)
    title = "📦 <b>Barcha buyurtmalar</b> (oxirgi 10 ta)" if code == "all" else f"📦 <b>{status_label(code)}</b> (oxirgi 10 ta)"
    text, kb = orders_list_view(orders, title, back=True)
    await safe_edit_text(cb.message, text, kb)
    await cb.answer()


@admin.callback_query(F.data.startswith("v:"))
async def a_view(cb: CallbackQuery, bot: Bot):
    oid = int(cb.data.split(":", 1)[1])
    if not db.get_order(oid):
        await cb.answer("Buyurtma topilmadi", show_alert=True)
        return
    await send_order_card(bot, cb.message.chat.id, oid)
    await cb.answer()


@admin.message(Command("qidirish"))
async def a_search(m: Message, command: CommandObject):
    q = (command.args or "").strip()
    if not q:
        await m.answer("Foydalanish: <code>/qidirish ism, telefon yoki buyurtma raqami</code>")
        return
    text, kb = orders_list_view(db.search_orders(q), f"🔎 <b>Qidiruv:</b> {esc(q)}")
    await m.answer(text, reply_markup=kb)


@admin.callback_query(F.data.startswith("st:"))
async def a_set_status(cb: CallbackQuery, bot: Bot):
    try:
        _, oid_s, code = cb.data.split(":")
        oid = int(oid_s)
    except ValueError:
        await cb.answer()
        return
    o = db.get_order(oid)
    if not o:
        await cb.answer("Buyurtma topilmadi", show_alert=True)
        return
    if code not in FLOW:
        await cb.answer("Noto'g'ri holat", show_alert=True)
        return
    if o["status"] in FINAL:
        await cb.answer("Bu buyurtma yakunlangan, holatini o'zgartirib bo'lmaydi.", show_alert=True)
        await safe_edit_text(cb.message, order_text(o, db.order_items(oid)), admin_order_kb(o))
        return
    if o["status"] == code:
        await cb.answer("Buyurtma allaqachon shu holatda.")
        return
    db.set_status(oid, code)
    log.info("Buyurtma №%s holati: %s -> %s (admin %s)", oid, o["status"], code, cb.from_user.id)
    o = db.get_order(oid)
    await cb.answer(f"Holat: {STATUSES[code]}")
    await safe_edit_text(cb.message, order_text(o, db.order_items(oid)), admin_order_kb(o))
    try:
        await bot.send_message(o["user_id"], USER_STATUS_MSG[code].format(oid=oid))
    except Exception:
        log.exception("Foydalanuvchiga (%s) holat xabari yuborilmadi", o["user_id"])


@admin.message(F.text == A_STATS)
async def a_stats(m: Message):
    s = db.stats()
    lines = [
        "📊 <b>Statistika</b>\n",
        f"📅 Bugun: <b>{s['today'][0]}</b> ta · {money(s['today'][1])} so'm",
        f"🗓 Shu oy: <b>{s['month'][0]}</b> ta · {money(s['month'][1])} so'm",
        f"🧮 Jami: <b>{s['total'][0]}</b> ta · {money(s['total'][1])} so'm",
        "<i>(summa bekor qilinganlarsiz hisoblangan)</i>",
        "\n<b>Holatlar bo'yicha:</b>",
    ]
    for code in STATUSES:
        lines.append(f"{status_label(code)}: {s['by_status'].get(code, 0)}")
    lines.append(f"\n👥 Ro'yxatdan o'tgan foydalanuvchilar: <b>{s['users']}</b>")
    await m.answer("\n".join(lines))


@admin.message(F.text == A_USERS)
async def a_users(m: Message):
    users = db.users_list(20)
    if not users:
        await m.answer("Hali foydalanuvchilar yo'q.")
        return
    lines = [f"👥 <b>Foydalanuvchilar</b>: jami {db.users_count()} ta (oxirgi 20 ta)\n"]
    for u in users:
        lines.append(
            f"• <a href=\"tg://user?id={u['tg_id']}\">{esc(u['name'])}</a> — {esc(u['phone'])} "
            f"— {fmt_dt(u['registered_at'])}"
        )
    await m.answer("\n".join(lines))


@admin.message(F.text == A_PRODUCTS)
async def a_products(m: Message):
    text, kb = products_view()
    await m.answer(text, reply_markup=kb)


@admin.callback_query(F.data.startswith("tg:"))
async def a_toggle(cb: CallbackQuery):
    db.toggle_product(int(cb.data.split(":", 1)[1]))
    text, kb = products_view()
    await safe_edit_text(cb.message, text, kb)
    await cb.answer("Saqlandi ✅")


@admin.message(Command("narx"))
async def a_price(m: Message, command: CommandObject):
    args = (command.args or "").split()
    if len(args) != 2 or not args[1].isdigit():
        await m.answer("Foydalanish: <code>/narx mint 230000</code>\nKalitlar: mint, classic, premium")
        return
    key, price = args[0].lower(), int(args[1])
    if not 1_000 <= price <= 100_000_000:
        await m.answer("❌ Narx 1 000 va 100 000 000 so'm oralig'ida bo'lishi kerak.")
        return
    if db.set_price(key, price):
        log.info("Narx o'zgardi: %s = %s (admin %s)", key, price, m.from_user.id)
        await m.answer(f"✅ <b>{esc(key)}</b> narxi {money(price)} so'm qilib o'zgartirildi.")
    else:
        await m.answer("❌ Bunday mahsulot topilmadi. Kalitlar: mint, classic, premium")


# ---------------------- Foydalanuvchi menyusi ----------------------
@user.message(F.text == BTN_CATALOG)
async def m_catalog(m: Message, bot: Bot):
    await send_catalog(bot, m.chat.id, m.from_user.id)


@user.callback_query(F.data == "catalog")
async def cb_catalog(cb: CallbackQuery, bot: Bot):
    await send_catalog(bot, cb.message.chat.id, cb.from_user.id)
    await cb.answer()


@user.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@user.callback_query(F.data.startswith("pi:"))
async def p_inc(cb: CallbackQuery):
    pid = int(cb.data.split(":", 1)[1])
    p = db.get_product(pid)
    if not p or not p["active"]:
        await cb.answer("Bu mahsulot hozircha mavjud emas.", show_alert=True)
        return
    qty = min(db.cart_qty(cb.from_user.id, pid) + 1, MAX_QTY)
    db.cart_set(cb.from_user.id, pid, qty)
    await safe_edit_markup(cb.message, product_kb(pid, qty))
    await cb.answer("Savatchaga qo'shildi ✅" if qty == 1 else f"Savatchada: {qty} ta")


@user.callback_query(F.data.startswith("pd:"))
async def p_dec(cb: CallbackQuery):
    pid = int(cb.data.split(":", 1)[1])
    qty = max(db.cart_qty(cb.from_user.id, pid) - 1, 0)
    db.cart_set(cb.from_user.id, pid, qty)
    await safe_edit_markup(cb.message, product_kb(pid, qty))
    await cb.answer("Savatchadan olib tashlandi" if qty == 0 else f"Savatchada: {qty} ta")


# ---------------------- Savatcha ----------------------
@user.message(F.text == BTN_CART)
async def m_cart(m: Message):
    text, kb = render_cart(m.from_user.id)
    await m.answer(text, reply_markup=kb)


@user.callback_query(F.data == "cart")
async def cb_cart(cb: CallbackQuery):
    text, kb = render_cart(cb.from_user.id)
    await safe_edit_text(cb.message, text, kb)
    await cb.answer()


@user.callback_query(F.data == "cart_edit")
async def cb_cart_edit(cb: CallbackQuery):
    text, kb = render_cart(cb.from_user.id, edit=True)
    await safe_edit_text(cb.message, text, kb)
    await cb.answer()


@user.callback_query(F.data.startswith(("ci:", "cd:", "cx:")))
async def cb_cart_change(cb: CallbackQuery):
    action, pid_s = cb.data.split(":", 1)
    pid, uid = int(pid_s), cb.from_user.id
    qty = db.cart_qty(uid, pid)
    if action == "ci":
        qty = min(qty + 1, MAX_QTY)
    elif action == "cd":
        qty -= 1
    else:
        qty = 0
    db.cart_set(uid, pid, qty)
    text, kb = render_cart(uid, edit=bool(db.cart_items(uid)))
    await safe_edit_text(cb.message, text, kb)
    await cb.answer()


@user.callback_query(F.data == "cart_clear")
async def cb_cart_clear(cb: CallbackQuery):
    db.cart_clear(cb.from_user.id)
    text, kb = render_cart(cb.from_user.id)
    await safe_edit_text(cb.message, text, kb)
    await cb.answer("Savatcha tozalandi")


# ---------------------- Buyurtma berish ----------------------
@user.callback_query(F.data == "checkout")
async def cb_checkout(cb: CallbackQuery, state: FSMContext):
    items = db.cart_items(cb.from_user.id)
    if not items:
        await cb.answer("Savatchangiz bo'sh.", show_alert=True)
        return
    text, _ = render_cart(cb.from_user.id)
    await state.set_state(Order.location)
    await cb.message.answer(
        text
        + "\n\n📍 Buyurtmani davom ettirish uchun joylashuvingizni yuboring.\n"
        "• «Joylashuvni yuborish» tugmasi — hozirgi joylashuvingiz\n"
        "• Boshqa manzil uchun: 📎 (qisqich) → «Joylashuv» → xaritadan joyni belgilab yuboring",
        reply_markup=location_kb(),
    )
    await cb.answer()


@user.message(Order.location, F.text == BTN_CANCEL)
async def order_cancel_text(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Buyurtma bekor qilindi. Savatchangiz saqlanib qoldi.", reply_markup=main_menu(is_admin(m.from_user.id)))


@user.message(Order.location, F.location)
async def order_got_location(m: Message, state: FSMContext):
    uid = m.from_user.id
    items = db.cart_items(uid)
    if not items:
        await state.clear()
        await m.answer("Savatchangiz bo'sh.", reply_markup=main_menu(is_admin(uid)))
        return
    total = sum(i["price"] * i["qty"] for i in items)
    lat, lon = m.location.latitude, m.location.longitude
    await state.update_data(lat=lat, lon=lon, total=total)
    await state.set_state(Order.confirm)
    row = db.get_user(uid)
    lines = ["🧾 <b>Buyurtmangizni tekshiring</b>\n"]
    for i, it in enumerate(items, 1):
        lines.append(
            f"{i}. {esc(it['name'])} — {it['qty']} × {money(it['price'])} = {money(it['qty'] * it['price'])} so'm"
        )
    lines += [
        f"\n💰 <b>Jami: {money(total)} so'm</b>",
        f"👤 Ism: {esc(row['name'])}",
        f"📞 Telefon: {esc(row['phone'])}",
        f"📍 Joylashuv: <code>{lat:.6f}, {lon:.6f}</code>",
        "\nHammasi to'g'rimi?",
    ]
    await m.answer("📍 Joylashuv qabul qilindi.", reply_markup=main_menu(is_admin(uid)))
    await m.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[btn("✅ Tasdiqlash", "ok_order"), btn("❌ Bekor qilish", "cancel_order")]]
        ),
    )


@user.message(Order.location)
async def order_need_location(m: Message):
    await m.answer(
        "📍 Buyurtmani yakunlash uchun joylashuvingiz kerak. "
        "Pastdagi «Joylashuvni yuborish» tugmasini bosing yoki bekor qiling.",
        reply_markup=location_kb(),
    )


@user.callback_query(Order.confirm, F.data == "ok_order")
async def order_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    try:
        status, oid = db.create_order(cb.from_user.id, data["lat"], data["lon"], data["total"])
    except KeyError:
        await safe_edit_text(cb.message, "Ma'lumotlar eskirgan. Savatchadan qaytadan boshlang.")
        await cb.answer()
        return
    if status == "empty":
        await safe_edit_text(cb.message, "Savatchangiz bo'sh yoki bu buyurtma allaqachon yaratilgan.")
    elif status == "changed":
        await safe_edit_text(
            cb.message,
            "⚠️ Savatcha yoki narxlar o'zgargan. Iltimos, savatchani qayta tekshirib, buyurtmani qaytadan bering.",
        )
    else:
        log.info("Yangi buyurtma №%s (foydalanuvchi %s)", oid, cb.from_user.id)
        await safe_edit_text(
            cb.message,
            f"✅ Buyurtmangiz qabul qilindi!\n\nBuyurtma raqami: <b>№{oid}</b>\n"
            "Tez orada siz bilan bog'lanamiz. Buyurtma holati o'zgarganda xabar beramiz.",
        )
        await notify_admins(bot, oid)
    await cb.answer()


@user.callback_query(Order.confirm, F.data == "cancel_order")
async def order_cancel_inline(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_text(cb.message, "Buyurtma bekor qilindi. Savatchangiz saqlanib qoldi.")
    await cb.answer()


@user.callback_query(F.data.in_({"ok_order", "cancel_order"}))
async def order_stale(cb: CallbackQuery):
    await cb.answer("Bu tugma eskirgan yoki buyurtma allaqachon yaratilgan.", show_alert=True)


# ---------------------- Buyurtmalarim va profil ----------------------
@user.message(F.text == BTN_ORDERS)
async def m_my_orders(m: Message):
    orders = db.list_orders(user_id=m.from_user.id, limit=10)
    if not orders:
        await m.answer("Siz hali buyurtma bermagansiz.")
        return
    parts = ["📦 <b>Buyurtmalarim</b> (oxirgi 10 ta)"]
    for o in orders:
        its = "\n".join(f"   • {esc(i['product_name'])} × {i['qty']}" for i in db.order_items(o["id"]))
        parts.append(
            f"\n<b>№{o['id']}</b> · {fmt_dt(o['created_at'])}\n{its}\n"
            f"   💰 {money(o['total'])} so'm · {status_label(o['status'])}"
        )
    await m.answer("\n".join(parts))


@user.message(F.text == BTN_PROFILE)
async def m_profile(m: Message):
    row = db.get_user(m.from_user.id)
    await m.answer(
        "👤 <b>Ma'lumotlaringiz</b>\n\n"
        f"Ism: {esc(row['name'])}\n"
        f"Telefon: {esc(row['phone'])}\n"
        f"Telegram ID: <code>{row['tg_id']}</code>\n"
        f"Ro'yxatdan o'tgan sana: {fmt_dt(row['registered_at'])}"
    )


@user.message(F.location)
async def stray_location(m: Message):
    await m.answer("Buyurtma berish uchun avval savatchadan «Buyurtma berish» tugmasini bosing.")


@user.message(F.text)
async def fallback(m: Message):
    await m.answer("Iltimos, pastdagi menyudan foydalaning.", reply_markup=main_menu(is_admin(m.from_user.id)))


# ====================== Ishga tushirish ======================
async def backup_loop() -> None:
    while True:
        try:
            dst = BACKUP_DIR / f"bot_{now_str()[:10].replace('-', '')}.db"
            db.backup(dst)
            for old in sorted(BACKUP_DIR.glob("bot_*.db"))[:-7]:  # oxirgi 7 ta nusxa saqlanadi
                old.unlink()
            log.info("Zaxira nusxa yaratildi: %s", dst.name)
        except Exception:
            log.exception("Zaxira nusxa yaratishda xatolik")
        await asyncio.sleep(24 * 3600)


async def main() -> None:
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    @dp.error()
    async def on_error(event: ErrorEvent):
        log.error("Kutilmagan xatolik: %s", event.exception, exc_info=event.exception)

    dp.include_router(reg)
    dp.include_router(admin)
    dp.include_router(user)

    await bot.set_my_commands([BotCommand(command="start", description="Botni ishga tushirish")])
    for aid in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Botni ishga tushirish"),
                    BotCommand(command="admin", description="Admin panel"),
                    BotCommand(command="narx", description="Narxni o'zgartirish"),
                    BotCommand(command="qidirish", description="Buyurtmani qidirish"),
                ],
                scope=BotCommandScopeChat(chat_id=aid),
            )
        except Exception:
            log.warning("Admin (%s) uchun buyruqlar o'rnatilmadi (admin hali /start bosmagan bo'lishi mumkin)", aid)

    backup_task = asyncio.create_task(backup_loop())
    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s", me.username)

    # Render yoki boshqa hostinglar uchun port tinglash (health check)
    port = os.getenv("PORT")
    web_runner = None
    if port:
        try:
            from aiohttp import web

            async def health(_req):
                return web.Response(text="ECO Bot 100% aktiv ishlamoqda!")

            srv = web.Application()
            srv.router.add_get("/", health)
            srv.router.add_get("/health", health)
            web_runner = web.AppRunner(srv)
            await web_runner.setup()
            site = web.TCPSite(web_runner, "0.0.0.0", int(port))
            await site.start()
            log.info("Health check server %s portda tinglamoqda", port)
        except Exception:
            log.exception("Health check serverni ishga tushirishda xatolik")

    try:
        await dp.start_polling(bot)
    finally:
        backup_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())