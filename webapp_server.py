"""ECO Telegram Mini App backend (aiohttp) — API va statik fayllar serveri."""
import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl

from aiohttp import web

from config import ADMIN_IDS, BASE_DIR, BOT_TOKEN, DB_PATH, MAX_QTY, WEBAPP_DIR, WEBAPP_HOST, WEBAPP_PORT
from db import Database

log = logging.getLogger("eco_webapp")

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
FLOW = ["accepted", "preparing", "delivering", "done", "cancelled"]
FINAL = {"done", "cancelled"}

PHONE_RE = re.compile(r"^\+?\d{9,15}$")
LOCAL_REMOTES = {"127.0.0.1", "::1"}
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
PROXY_HEADERS = ("X-Forwarded-For", "Forwarded", "CF-Connecting-IP", "X-Real-IP")
INIT_DATA_TTL_SEC = 86400

NotifyAdminsCb = Callable[[int], Awaitable[None]]
NotifyUserStatusCb = Callable[[int, int, str], Awaitable[None]]


def _json_error(message: str, status: int = 400, code: str = "bad_request") -> web.Response:
    return web.json_response({"ok": False, "error": message, "code": code}, status=status)


def _is_local_preview_request(request: web.Request) -> bool:
    """Faqat to'g'ridan-to'g'ri localhost so'rovlariga demo ko'rinishga ruxsat beradi."""
    if request.remote not in LOCAL_REMOTES:
        return False
    if any(h in request.headers for h in PROXY_HEADERS):
        return False
    host = request.headers.get("Host", "").split(":")[0].lower()
    return host in LOCAL_HOSTS


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Telegram WebApp initData imzosini HMAC-SHA256 orqali tekshiradi."""
    if not init_data:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date <= 0 or abs(time.time() - auth_date) > INIT_DATA_TTL_SEC:
        return None

    raw_user = pairs.get("user")
    if not raw_user:
        return None
    try:
        tg_user = json.loads(raw_user)
        uid = int(tg_user["id"])
    except (ValueError, KeyError, TypeError):
        return None

    first = str(tg_user.get("first_name", "")).strip()
    last = str(tg_user.get("last_name", "")).strip()
    full_name = f"{first} {last}".strip() or str(tg_user.get("username") or f"User {uid}")
    return {"id": uid, "name": full_name, "username": tg_user.get("username")}


def normalize_phone(raw: str) -> str | None:
    cleaned = re.sub(r"[\s\-()]+", "", (raw or "").strip())
    if not PHONE_RE.match(cleaned):
        return None
    return cleaned if cleaned.startswith("+") else f"+{cleaned}"


class WebAppHandler:
    def __init__(
        self,
        db: Database,
        notify_admins_cb: NotifyAdminsCb | None = None,
        notify_user_status_cb: NotifyUserStatusCb | None = None,
    ):
        self.db = db
        self.notify_admins_cb = notify_admins_cb
        self.notify_user_status_cb = notify_user_status_cb

    def _resolve_auth(self, request: web.Request) -> dict:
        init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
        if init_data:
            tg_user = verify_telegram_init_data(init_data, BOT_TOKEN)
            if not tg_user:
                raise web.HTTPUnauthorized(
                    text=json.dumps({"ok": False, "error": "Telegram sessiyasi yaroqsiz yoki eskirgan.", "code": "invalid_init_data"}),
                    content_type="application/json",
                )
            self.db.touch_user(tg_user["id"], tg_user["name"])
            return {
                "id": tg_user["id"],
                "name": tg_user["name"],
                "is_admin": tg_user["id"] in ADMIN_IDS,
                "source": "telegram",
            }

        if _is_local_preview_request(request):
            demo_role = request.headers.get("X-Demo-Role", "customer").strip().lower()
            if demo_role == "admin" and ADMIN_IDS:
                uid = sorted(ADMIN_IDS)[0]
                default_name = "ECO Admin (Demo)"
            else:
                uid = 999000111
                default_name = "Mehmon Mijoz (Demo)"
            self.db.touch_user(uid, default_name)
            return {
                "id": uid,
                "name": default_name,
                "is_admin": uid in ADMIN_IDS,
                "source": "local_demo",
            }

        raise web.HTTPUnauthorized(
            text=json.dumps(
                {
                    "ok": False,
                    "error": "Ushbu do'konni faqat Telegram Mini App orqali ochish mumkin.",
                    "code": "telegram_required",
                }
            ),
            content_type="application/json",
        )

    def _serialize_user(self, auth: dict) -> dict:
        row = self.db.get_user(auth["id"])
        return {
            "tg_id": auth["id"],
            "name": row["name"] if row else auth["name"],
            "phone": row["phone"] if row else None,
            "age_ok": bool(row["age_ok"]) if row else False,
            "is_registered": bool(row and row["phone"]),
            "registered_at": row["registered_at"] if row else None,
            "is_admin": auth["is_admin"],
            "auth_source": auth["source"],
        }

    def _serialize_product(self, p) -> dict:
        image_rel = (p["image"] or "").lstrip("/")
        return {
            "id": p["id"],
            "key": p["key"],
            "name": p["name"],
            "description": p["description"],
            "price": p["price"],
            "image_url": f"/{image_rel}" if image_rel else None,
            "active": bool(p["active"]),
        }

    def _serialize_cart(self, uid: int) -> dict:
        rows = self.db.cart_items(uid)
        products_by_id = {p["id"]: p for p in self.db.products(active_only=False)}
        items = []
        total = 0
        total_qty = 0
        for row in rows:
            pid = row["product_id"]
            p = products_by_id.get(pid)
            image_rel = ((p["image"] if p else "") or "").lstrip("/")
            subtotal = row["price"] * row["qty"]
            total += subtotal
            total_qty += row["qty"]
            items.append(
                {
                    "product_id": pid,
                    "key": p["key"] if p else "",
                    "name": row["name"],
                    "price": row["price"],
                    "qty": row["qty"],
                    "subtotal": subtotal,
                    "image_url": f"/{image_rel}" if image_rel else None,
                }
            )
        return {
            "items": items,
            "total": total,
            "total_qty": total_qty,
            "max_qty": MAX_QTY,
        }

    def _serialize_order(self, o) -> dict:
        items = self.db.order_items(o["id"])
        return {
            "id": o["id"],
            "user_id": o["user_id"],
            "user_name": o["user_name"],
            "phone": o["phone"],
            "total": o["total"],
            "lat": o["lat"],
            "lon": o["lon"],
            "status": o["status"],
            "status_label": STATUSES.get(o["status"], o["status"]),
            "status_emoji": STATUS_EMOJI.get(o["status"], ""),
            "is_final": o["status"] in FINAL,
            "created_at": o["created_at"],
            "items": [
                {
                    "product_name": it["product_name"],
                    "price": it["price"],
                    "qty": it["qty"],
                    "subtotal": it["price"] * it["qty"],
                }
                for it in items
            ],
        }

    async def index(self, request: web.Request) -> web.Response:
        index_path = WEBAPP_DIR / "index.html"
        if not index_path.exists():
            return web.Response(text="WebApp topilmadi", status=404)
        return web.FileResponse(index_path, headers={"Cache-Control": "no-cache"})

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def bootstrap(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        products = [self._serialize_product(p) for p in self.db.products(active_only=True)]
        orders = [self._serialize_order(o) for o in self.db.list_orders(user_id=uid, limit=20)]
        return web.json_response(
            {
                "ok": True,
                "user": self._serialize_user(auth),
                "products": products,
                "cart": self._serialize_cart(uid),
                "orders": orders,
                "statuses": {
                    code: {"label": STATUSES[code], "emoji": STATUS_EMOJI[code]}
                    for code in STATUSES
                },
                "flow": FLOW,
            }
        )

    async def age_confirm(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        self.db.set_age_ok(auth["id"])
        return web.json_response({"ok": True, "user": self._serialize_user(auth)})

    async def register_user(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        try:
            data = await request.json()
        except Exception:
            return _json_error("Noto'g'ri JSON so'rov.")

        name = str(data.get("name") or auth["name"]).strip()[:80]
        phone = normalize_phone(str(data.get("phone") or ""))
        if not name:
            return _json_error("Iltimos, ismingizni kiriting.")
        if not phone:
            return _json_error("Telefon raqamingizni to'g'ri kiriting (masalan: +998901234567).")

        self.db.touch_user(auth["id"], name)
        self.db.set_age_ok(auth["id"])
        self.db.register(auth["id"], name, phone)
        log.info("Mini App ro'yxatdan o'tish/yangilash: %s (%s)", auth["id"], phone)
        return web.json_response({"ok": True, "user": self._serialize_user(auth)})

    async def set_cart_item(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        try:
            data = await request.json()
            pid = int(data["product_id"])
            qty = int(data["qty"])
        except Exception:
            return _json_error("Mahsulot va miqdor ko'rsatilishi kerak.")

        qty = max(0, min(qty, MAX_QTY))
        if qty > 0:
            product = self.db.get_product(pid)
            if not product or not product["active"]:
                return _json_error("Bu mahsulot hozircha mavjud emas.", status=404)

        self.db.cart_set(auth["id"], pid, qty)
        return web.json_response({"ok": True, "cart": self._serialize_cart(auth["id"])})

    async def clear_cart(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        self.db.cart_clear(auth["id"])
        return web.json_response({"ok": True, "cart": self._serialize_cart(auth["id"])})

    async def list_my_orders(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        orders = [self._serialize_order(o) for o in self.db.list_orders(user_id=auth["id"], limit=25)]
        return web.json_response({"ok": True, "orders": orders})

    async def create_order(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        user = self.db.get_user(uid)
        if not user or not user["age_ok"]:
            return _json_error("Davom etish uchun 21 yoshdan oshganingizni tasdiqlang.", code="age_required")
        if not user["phone"]:
            return _json_error("Buyurtma berish uchun telefon raqamingizni kiriting.", code="phone_required")

        try:
            data = await request.json()
            lat = float(data["lat"])
            lon = float(data["lon"])
            expected_total = int(data["expected_total"])
        except Exception:
            return _json_error("Joylashuv va buyurtma summasi to'g'ri yuborilmadi.")

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return _json_error("Joylashuv koordinatalari noto'g'ri.")

        status, oid = self.db.create_order(uid, lat, lon, expected_total)
        if status == "empty":
            return _json_error("Savatchangiz bo'sh.", code="empty_cart")
        if status == "changed":
            return _json_error(
                "Savatcha yoki narxlar o'zgargan. Sahifa yangilandi, qayta tekshiring.",
                status=409,
                code="price_changed",
            )

        log.info("Mini App yangi buyurtma №%s (foydalanuvchi %s)", oid, uid)
        if self.notify_admins_cb and oid is not None:
            asyncio.create_task(self.notify_admins_cb(oid))

        order = self._serialize_order(self.db.get_order(oid))
        return web.json_response(
            {
                "ok": True,
                "order": order,
                "cart": self._serialize_cart(uid),
            }
        )

    # ---------------------- Admin API ----------------------
    def _require_admin(self, request: web.Request) -> dict:
        auth = self._resolve_auth(request)
        if not auth["is_admin"]:
            raise web.HTTPForbidden(
                text=json.dumps({"ok": False, "error": "Faqat adminlar uchun ruxsat berilgan."}),
                content_type="application/json",
            )
        return auth

    async def admin_overview(self, request: web.Request) -> web.Response:
        self._require_admin(request)
        status_filter = request.query.get("status", "all").strip()
        q = request.query.get("q", "").strip()

        if q:
            raw_orders = self.db.search_orders(q, limit=30)
        elif status_filter and status_filter != "all":
            if status_filter not in STATUSES:
                return _json_error("Noto'g'ri buyurtma holati.")
            raw_orders = self.db.list_orders(status=status_filter, limit=30)
        else:
            raw_orders = self.db.list_orders(limit=30)

        users = [
            {
                "tg_id": u["tg_id"],
                "name": u["name"],
                "phone": u["phone"],
                "registered_at": u["registered_at"],
            }
            for u in self.db.users_list(50)
        ]

        return web.json_response(
            {
                "ok": True,
                "stats": self.db.stats(),
                "orders": [self._serialize_order(o) for o in raw_orders],
                "products": [self._serialize_product(p) for p in self.db.products(active_only=False)],
                "users": users,
            }
        )

    async def admin_set_order_status(self, request: web.Request) -> web.Response:
        auth = self._require_admin(request)
        try:
            oid = int(request.match_info["id"])
            data = await request.json()
            code = str(data.get("status", "")).strip()
        except Exception:
            return _json_error("Noto'g'ri so'rov.")

        if code not in FLOW:
            return _json_error("Noto'g'ri holat kodi.")

        o = self.db.get_order(oid)
        if not o:
            return _json_error("Buyurtma topilmadi.", status=404)
        if o["status"] in FINAL:
            return _json_error("Yakunlangan buyurtma holatini o'zgartirib bo'lmaydi.")
        if o["status"] == code:
            return web.json_response({"ok": True, "order": self._serialize_order(o), "stats": self.db.stats()})

        self.db.set_status(oid, code)
        log.info("Mini App buyurtma №%s holati: %s -> %s (admin %s)", oid, o["status"], code, auth["id"])
        updated = self.db.get_order(oid)

        if self.notify_user_status_cb:
            asyncio.create_task(self.notify_user_status_cb(updated["user_id"], oid, code))

        return web.json_response(
            {
                "ok": True,
                "order": self._serialize_order(updated),
                "stats": self.db.stats(),
            }
        )

    async def admin_toggle_product(self, request: web.Request) -> web.Response:
        self._require_admin(request)
        try:
            pid = int(request.match_info["id"])
        except ValueError:
            return _json_error("Noto'g'ri mahsulot ID.")
        if not self.db.get_product(pid):
            return _json_error("Mahsulot topilmadi.", status=404)
        self.db.toggle_product(pid)
        return web.json_response(
            {
                "ok": True,
                "products": [self._serialize_product(p) for p in self.db.products(active_only=False)],
            }
        )

    async def admin_set_product_price(self, request: web.Request) -> web.Response:
        auth = self._require_admin(request)
        try:
            pid = int(request.match_info["id"])
            data = await request.json()
            price = int(data["price"])
        except Exception:
            return _json_error("Narx butun son ko'rinishida kiritilishi kerak.")

        if not 1_000 <= price <= 100_000_000:
            return _json_error("Narx 1 000 va 100 000 000 so'm oralig'ida bo'lishi kerak.")

        if not self.db.set_price_by_id(pid, price):
            return _json_error("Mahsulot topilmadi.", status=404)

        log.info("Mini App narx o'zgardi: id=%s price=%s (admin %s)", pid, price, auth["id"])
        return web.json_response(
            {
                "ok": True,
                "products": [self._serialize_product(p) for p in self.db.products(active_only=False)],
            }
        )


def create_webapp(
    db: Database,
    notify_admins_cb: NotifyAdminsCb | None = None,
    notify_user_status_cb: NotifyUserStatusCb | None = None,
) -> web.Application:
    app = web.Application()
    h = WebAppHandler(db, notify_admins_cb=notify_admins_cb, notify_user_status_cb=notify_user_status_cb)

    app.router.add_get("/", h.index)
    app.router.add_get("/health", h.health)
    app.router.add_get("/api/health", h.health)
    app.router.add_get("/api/bootstrap", h.bootstrap)
    app.router.add_post("/api/age-confirm", h.age_confirm)
    app.router.add_post("/api/register", h.register_user)
    app.router.add_post("/api/cart", h.set_cart_item)
    app.router.add_delete("/api/cart", h.clear_cart)
    app.router.add_get("/api/orders", h.list_my_orders)
    app.router.add_post("/api/orders", h.create_order)

    app.router.add_get("/api/admin/overview", h.admin_overview)
    app.router.add_post("/api/admin/orders/{id}/status", h.admin_set_order_status)
    app.router.add_post("/api/admin/products/{id}/toggle", h.admin_toggle_product)
    app.router.add_post("/api/admin/products/{id}/price", h.admin_set_product_price)

    WEBAPP_DIR.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/static", WEBAPP_DIR, show_index=False)

    images_dir = BASE_DIR / "images"
    if images_dir.exists():
        app.router.add_static("/images", images_dir, show_index=False)

    return app


async def run_standalone() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    db = Database(DB_PATH)
    app = create_webapp(db)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    log.info("Mini App server ishga tushdi: http://%s:%s", WEBAPP_HOST, WEBAPP_PORT)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run_standalone())
