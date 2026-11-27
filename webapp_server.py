"""Telegram Mini App va SuperAdmin/Diler boshqaruv tizimi uchun REST API backend server (aiohttp)."""
import asyncio
import csv
import hashlib
import hmac
import io
import json
import logging
import re
from typing import Awaitable, Callable
from urllib.parse import parse_qsl

from aiohttp import web

from config import (
    ADMIN_IDS,
    BASE_DIR,
    BOT_TOKEN,
    DB_PATH,
    MAX_QTY,
    SUPERADMIN_IDS,
    WEBAPP_DIR,
    WEBAPP_HOST,
    WEBAPP_PORT,
)
from db import Database

log = logging.getLogger("eco_webapp")

PHONE_RE = re.compile(r"^\+?998\d{9}$")
STATUSES = {
    "new": "Yangi",
    "new_unassigned": "Dilersiz (Kutilmoqda)",
    "accepted": "Qabul qilindi",
    "preparing": "Tayyorlanmoqda",
    "delivering": "Yetkazilmoqda",
    "done": "Yakunlandi",
    "cancelled": "Bekor qilindi",
    "returned": "Qaytarildi",
}
STATUS_EMOJI = {
    "new": "🆕",
    "new_unassigned": "⚠️",
    "accepted": "✅",
    "preparing": "👨‍🍳",
    "delivering": "🚚",
    "done": "🎉",
    "cancelled": "❌",
    "returned": "🔄",
}
FLOW = ["accepted", "preparing", "delivering", "done", "cancelled", "returned"]
FINAL = {"done", "cancelled", "returned"}

LOCAL_REMOTES = {"127.0.0.1", "::1"}
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
PROXY_HEADERS = ("X-Forwarded-For", "Forwarded", "CF-Connecting-IP", "X-Real-IP")

NotifyAdminsCb = Callable[[int], Awaitable[None]]
NotifyDealerCb = Callable[[int, int], Awaitable[None]]
NotifyUserStatusCb = Callable[[int, int, str], Awaitable[None]]
NotifyDiscrepancyCb = Callable[[int, int, str], Awaitable[None]]


def _json_error(message: str, status: int = 400, code: str = "bad_request") -> web.Response:
    return web.json_response({"ok": False, "error": message, "code": code}, status=status)


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
        log.warning("HMAC mismatch: expected=%s, got=%s", expected_hash, received_hash)
        return None

    raw_user = pairs.get("user")
    if not raw_user:
        return None
    try:
        tg_user = json.loads(raw_user)
        uid = int(tg_user["id"])
    except (ValueError, KeyError, TypeError) as e:
        log.warning("Failed parsing tg_user: %s", e)
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
        notify_dealer_cb: NotifyDealerCb | None = None,
        notify_user_status_cb: NotifyUserStatusCb | None = None,
        notify_discrepancy_cb: NotifyDiscrepancyCb | None = None,
    ):
        self.db = db
        self.notify_admins_cb = notify_admins_cb
        self.notify_dealer_cb = notify_dealer_cb
        self.notify_user_status_cb = notify_user_status_cb
        self.notify_discrepancy_cb = notify_discrepancy_cb

    def _resolve_auth(self, request: web.Request) -> dict:
        init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
        if init_data:
            tg_user = verify_telegram_init_data(init_data, BOT_TOKEN)
            if tg_user:
                uid = tg_user["id"]
                name = tg_user["name"]
                self.db.touch_user(uid, name)

                is_superadmin = uid in SUPERADMIN_IDS
                dealer = self.db.get_dealer_by_tg_id(uid)
                is_dealer = dealer is not None

                role = "superadmin" if is_superadmin else ("dealer" if is_dealer else "customer")

                return {
                    "id": uid,
                    "name": name,
                    "is_admin": is_superadmin or is_dealer,
                    "is_superadmin": is_superadmin,
                    "is_dealer": is_dealer,
                    "dealer_id": dealer["id"] if dealer else None,
                    "region_id": dealer["region_id"] if dealer else None,
                    "dealer_info": dict(dealer) if dealer else None,
                    "role": role,
                    "source": "telegram",
                }
            log.warning("init_data mavjud, ammo tasdiqlanmadi.")

        # Mehmon foydalanuvchi (faqat ko'rish va xarid uchun)
        client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or request.remote or "guest"
        guest_id = (abs(hash(client_ip)) % 800_000_000) + 100_000_000
        default_name = "Mijoz"
        self.db.touch_user(guest_id, default_name)
        return {
            "id": guest_id,
            "name": default_name,
            "is_admin": False,
            "is_superadmin": False,
            "is_dealer": False,
            "dealer_id": None,
            "region_id": None,
            "dealer_info": None,
            "role": "customer",
            "source": "guest",
        }

    def _require_superadmin(self, request: web.Request) -> dict:
        auth = self._resolve_auth(request)
        if not auth["is_superadmin"]:
            raise web.HTTPForbidden(
                text=json.dumps({"ok": False, "error": "Faqat SuperAdmin (Zavod boshqaruvchisi) uchun ruxsat berilgan."}),
                content_type="application/json",
            )
        return auth

    def _require_dealer(self, request: web.Request) -> dict:
        auth = self._resolve_auth(request)
        if not (auth["is_dealer"] or auth["is_superadmin"]):
            raise web.HTTPForbidden(
                text=json.dumps({"ok": False, "error": "Faqat hududiy dilerlar uchun ruxsat berilgan."}),
                content_type="application/json",
            )
        return auth

    def _require_any_admin(self, request: web.Request) -> dict:
        auth = self._resolve_auth(request)
        if not auth["is_admin"]:
            raise web.HTTPForbidden(
                text=json.dumps({"ok": False, "error": "Faqat adminlar uchun ruxsat berilgan."}),
                content_type="application/json",
            )
        return auth

    def _serialize_user(self, auth: dict) -> dict:
        row = self.db.get_user(auth["id"])
        reg_id = row["region_id"] if row else None
        region = self.db.get_region(reg_id) if reg_id else None
        return {
            "tg_id": auth["id"],
            "name": row["name"] if row else auth["name"],
            "phone": row["phone"] if row else None,
            "age_ok": bool(row["age_ok"]) if row else False,
            "region_id": reg_id,
            "region_name": region["name"] if region else None,
            "district": row["district"] if row else None,
            "is_registered": bool(row and row["phone"] and row["region_id"]),
            "registered_at": row["registered_at"] if row else None,
            "is_admin": auth["is_admin"],
            "is_superadmin": auth["is_superadmin"],
            "is_dealer": auth["is_dealer"],
            "dealer_info": auth["dealer_info"],
            "role": auth["role"],
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
            "cost_price": p["cost_price"],
            "wholesale_price": p["wholesale_price"],
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
            "region_id": o["region_id"],
            "region_name": o["region_name"] if "region_name" in o.keys() else None,
            "district": o["district"],
            "dealer_id": o["dealer_id"],
            "dealer_name": o["dealer_name"] if "dealer_name" in o.keys() else None,
            "total": o["total"],
            "lat": o["lat"],
            "lon": o["lon"],
            "status": o["status"],
            "status_label": STATUSES.get(o["status"], o["status"]),
            "status_emoji": STATUS_EMOJI.get(o["status"], ""),
            "payment_status": o["payment_status"],
            "payment_method": o["payment_method"],
            "paid_amount": o["paid_amount"],
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

    # ==================== UMUMIY / MIJOZ API ====================
    async def get_regions_list(self, request: web.Request) -> web.Response:
        """14 ta hudud va ularning tumanlari ro'yxati."""
        regions = self.db.get_regions(active_only=True)
        res = []
        for r in regions:
            try:
                districts = json.loads(r["districts_json"])
            except Exception:
                districts = []
            res.append({"id": r["id"], "name": r["name"], "code": r["code"], "districts": districts})
        return web.json_response({"ok": True, "regions": res})

    async def bootstrap(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        user_info = self._serialize_user(auth)
        products = [self._serialize_product(p) for p in self.db.products(active_only=True)]
        cart = self._serialize_cart(uid)
        orders = [self._serialize_order(o) for o in self.db.list_orders(user_id=uid, limit=20)]

        regions = []
        for r in self.db.get_regions(active_only=True):
            try:
                d_list = json.loads(r["districts_json"])
            except Exception:
                d_list = []
            regions.append({"id": r["id"], "name": r["name"], "code": r["code"], "districts": d_list})

        return web.json_response(
            {
                "ok": True,
                "user": user_info,
                "products": products,
                "cart": cart,
                "orders": orders,
                "regions": regions,
                "statuses": {
                    k: {"label": STATUSES[k], "emoji": STATUS_EMOJI.get(k, "")}
                    for k in STATUSES
                },
                "flow": FLOW,
            }
        )

    async def age_confirm(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        self.db.set_age_ok(uid)
        return web.json_response({"ok": True, "user": self._serialize_user(auth)})

    async def register_user(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        try:
            data = await request.json()
            name = str(data.get("name", "")).strip()
            raw_phone = str(data.get("phone", "")).strip()
            region_id = int(data.get("region_id", 0)) if data.get("region_id") else None
            district = str(data.get("district", "")).strip() or None
        except Exception:
            return _json_error("Noto'g'ri so'rov formati.")

        if not name or len(name) < 2:
            return _json_error("Ismingizni to'liq kiriting.")

        phone = normalize_phone(raw_phone)
        if not phone:
            return _json_error("Telefon raqami noto'g'ri (+998XXXXXXXXX ko'rinishida kiriting).")

        if not region_id:
            return _json_error("Iltimos, viloyatingizni tanlang.")

        self.db.register(uid, name, phone, region_id, district)
        log.info("Foydalanuvchi ma'lumotlari saqlandi: id=%s name=%s region=%s", uid, name, region_id)
        return web.json_response({"ok": True, "user": self._serialize_user(auth)})

    async def save_user_region(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        try:
            data = await request.json()
            region_id = int(data.get("region_id", 0))
            district = str(data.get("district", "")).strip()
        except Exception:
            return _json_error("Noto'g'ri so'rov.")

        if not region_id or not self.db.get_region(region_id):
            return _json_error("Noto'g'ri viloyat tanlandi.")

        self.db.set_user_region(uid, region_id, district)
        return web.json_response({"ok": True, "user": self._serialize_user(auth)})

    async def set_cart_item(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        uid = auth["id"]
        try:
            data = await request.json()
            pid = int(data["product_id"])
            qty = int(data["qty"])
        except Exception:
            return _json_error("Mahsulot va miqdor to'g'ri ko'rsatilmadi.")

        if qty < 0:
            qty = 0
        elif qty > MAX_QTY:
            return _json_error(f"Bitta mahsulotdan ko'pi bilan {MAX_QTY} dona buyurtma berish mumkin.")

        self.db.cart_set(uid, pid, qty)
        return web.json_response({"ok": True, "cart": self._serialize_cart(uid)})

    async def clear_cart(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        self.db.cart_clear(auth["id"])
        return web.json_response({"ok": True, "cart": self._serialize_cart(auth["id"])})

    async def list_my_orders(self, request: web.Request) -> web.Response:
        auth = self._resolve_auth(request)
        orders = self.db.list_orders(user_id=auth["id"], limit=30)
        return web.json_response({"ok": True, "orders": [self._serialize_order(o) for o in orders]})

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
            region_id = int(data.get("region_id", 0)) if data.get("region_id") else user["region_id"]
            district = str(data.get("district", "")).strip() or user["district"]
            payment_method = str(data.get("payment_method", "cash")).strip()
        except Exception:
            return _json_error("Joylashuv va buyurtma summasi to'g'ri yuborilmadi.")

        if not region_id:
            return _json_error("Yetkazib berish viloyatini tanlang.", code="region_required")

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return _json_error("Joylashuv koordinatalari noto'g'ri.")

        status, oid, dealer_id = self.db.create_order(
            uid=uid,
            lat=lat,
            lon=lon,
            expected_total=expected_total,
            region_id=region_id,
            district=district,
            payment_method=payment_method,
        )

        if status == "empty":
            return _json_error("Savatchangiz bo'sh.", code="empty_cart")
        if status == "changed":
            return _json_error("Savatcha yoki narxlar o'zgargan. Qayta tekshiring.", status=409, code="price_changed")
        if status == "out_of_stock":
            return _json_error(
                "Kechirasiz, hududingizdagi diler omborida ushbu mahsulotdan yetarli miqdor qolmagan. Iltimos, miqdorni kamaytiring yoki diler bilan bog'laning.",
                code="out_of_stock",
            )

        log.info("Yangi buyurtma №%s (mijoz %s, hudud %s, diler %s)", oid, uid, region_id, dealer_id)

        # Xabarnoma yuborish: Agar diler bo'lsa dilerga, aks holda SuperAdminga
        if dealer_id and self.notify_dealer_cb and oid is not None:
            asyncio.create_task(self.notify_dealer_cb(dealer_id, oid))
        elif self.notify_admins_cb and oid is not None:
            asyncio.create_task(self.notify_admins_cb(oid))

        order = self._serialize_order(self.db.get_order(oid))
        return web.json_response(
            {
                "ok": True,
                "order": order,
                "cart": self._serialize_cart(uid),
            }
        )

    # ==================== SUPERADMIN API (ZAVOD BOSHQARUVI) ====================
    async def superadmin_overview(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        analytics = self.db.superadmin_analytics()
        factory_inventory = [dict(r) for r in self.db.get_factory_inventory()]
        dealers = [dict(r) for r in self.db.get_dealers()]
        recent_shipments = [dict(r) for r in self.db.list_shipments(limit=10)]
        recent_orders = [self._serialize_order(o) for o in self.db.list_orders(limit=15)]
        products = [self._serialize_product(p) for p in self.db.products(active_only=False)]

        return web.json_response(
            {
                "ok": True,
                "analytics": analytics,
                "factory_inventory": factory_inventory,
                "dealers": dealers,
                "recent_shipments": recent_shipments,
                "recent_orders": recent_orders,
                "products": products,
            }
        )

    async def superadmin_get_dealers(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        dealers = [dict(r) for r in self.db.get_dealers()]
        regions = [dict(r) for r in self.db.get_regions(active_only=False)]
        return web.json_response({"ok": True, "dealers": dealers, "regions": regions})

    async def superadmin_save_dealer(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        try:
            data = await request.json()
            region_id = int(data["region_id"])
            tg_id = int(data["tg_id"])
            name = str(data["name"]).strip()
            phone = str(data.get("phone", "")).strip()
            wholesale_model = str(data.get("wholesale_model", "consignment")).strip()
            status = str(data.get("status", "active")).strip()
        except Exception:
            return _json_error("Ma'lumotlar to'liq kiritilmadi.")

        did = self.db.upsert_dealer(
            region_id=region_id,
            tg_id=tg_id,
            name=name,
            phone=phone,
            wholesale_model=wholesale_model,
            status=status,
            actor_id=auth["id"],
        )
        return web.json_response({"ok": True, "dealer": dict(self.db.get_dealer(did))})

    async def superadmin_set_dealer_status(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        did = int(request.match_info["id"])
        data = await request.json()
        status = str(data.get("status", "active")).strip()
        self.db.set_dealer_status(did, status, actor_id=auth["id"])
        return web.json_response({"ok": True, "dealer": dict(self.db.get_dealer(did))})

    async def superadmin_delete_dealer(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        did = int(request.match_info["id"])
        self.db.delete_dealer(did, actor_id=auth["id"])
        return web.json_response({"ok": True})

    async def superadmin_factory_inventory(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        inventory = [dict(r) for r in self.db.get_factory_inventory()]
        return web.json_response({"ok": True, "inventory": inventory})

    async def superadmin_adjust_factory_inventory(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        try:
            data = await request.json()
            pid = int(data["product_id"])
            change_qty = int(data["change_qty"])
            reason = str(data.get("reason", "Qo'lda tuzatish")).strip()
        except Exception:
            return _json_error("Mahsulot va miqdor to'g'ri kiritilmadi.")

        new_stock = self.db.adjust_factory_stock(pid, change_qty, reason, actor_id=auth["id"])
        return web.json_response({"ok": True, "new_stock": new_stock})

    async def superadmin_list_shipments(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        status_filter = request.query.get("status")
        dealer_id = int(request.query["dealer_id"]) if "dealer_id" in request.query and request.query["dealer_id"].isdigit() else None
        shipments = [dict(s) for s in self.db.list_shipments(dealer_id=dealer_id, status=status_filter, limit=100)]
        return web.json_response({"ok": True, "shipments": shipments})

    async def superadmin_create_shipment(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        try:
            data = await request.json()
            dealer_id = int(data["dealer_id"])
            items = data["items"]  # [{product_id, sent_qty, unit_price}]
            notes = str(data.get("notes", "")).strip()
        except Exception:
            return _json_error("Jo'natma ma'lumotlari to'g'ri kiritilmadi.")

        if not items:
            return _json_error("Kamida bitta mahsulot tanlanishi kerak.")

        ok, msg, shp_id = self.db.create_shipment(
            dealer_id=dealer_id,
            items=items,
            notes=notes,
            actor_id=auth["id"],
        )
        if not ok:
            return _json_error(msg)

        shipment = dict(self.db.get_shipment(shp_id))
        shipment["items"] = [dict(it) for it in self.db.get_shipment_items(shp_id)]
        return web.json_response({"ok": True, "shipment": shipment})

    async def superadmin_dealer_finance(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        did = int(request.match_info["id"])
        summary = self.db.get_dealer_finance_summary(did)
        ledger = [dict(r) for r in self.db.get_dealer_ledger(did, limit=50)]
        return web.json_response({"ok": True, "summary": summary, "ledger": ledger})

    async def superadmin_record_dealer_payment(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        did = int(request.match_info["id"])
        try:
            data = await request.json()
            amount = int(data["amount"])
            payment_method = str(data.get("payment_method", "cash")).strip()
            note = str(data.get("note", "")).strip()
        except Exception:
            return _json_error("To'lov summasi to'g'ri kiritilmadi.")

        if amount <= 0:
            return _json_error("To'lov summasi noldan katta bo'lishi kerak.")

        fid = self.db.record_dealer_payment(
            dealer_id=did,
            amount=amount,
            payment_method=payment_method,
            note=note,
            actor_id=auth["id"],
        )
        summary = self.db.get_dealer_finance_summary(did)
        return web.json_response({"ok": True, "payment_id": fid, "summary": summary})

    async def superadmin_manage_products(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        products = [self._serialize_product(p) for p in self.db.products(active_only=False)]
        return web.json_response({"ok": True, "products": products})

    async def superadmin_create_product(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        try:
            data = await request.json()
            key = str(data["key"]).strip().lower()
            name = str(data["name"]).strip()
            desc = str(data.get("description", "")).strip()
            price = int(data["price"])
            cost = int(data.get("cost_price", int(price * 0.65)))
            wholesale = int(data.get("wholesale_price", int(price * 0.85)))
            image = str(data.get("image", "")).strip()
        except Exception:
            return _json_error("Mahsulot ma'lumotlari to'liq kiritilmadi.")

        try:
            pid = self.db.create_product(key, name, desc, price, cost, wholesale, image)
            self.db.log_audit(auth["id"], "create_product", "products", pid, {"name": name, "price": price})
            return web.json_response({"ok": True, "product": self._serialize_product(self.db.get_product(pid))})
        except Exception as e:
            return _json_error(f"Mahsulot yaratishda xatolik: {e}")

    async def superadmin_update_product(self, request: web.Request) -> web.Response:
        auth = self._require_superadmin(request)
        pid = int(request.match_info["id"])
        try:
            data = await request.json()
            name = str(data["name"]).strip()
            desc = str(data.get("description", "")).strip()
            price = int(data["price"])
            cost = int(data["cost_price"])
            wholesale = int(data["wholesale_price"])
            active = 1 if data.get("active", True) else 0
        except Exception:
            return _json_error("Mahsulot ma'lumotlari to'liq kiritilmadi.")

        ok = self.db.update_product(pid, name, desc, price, cost, wholesale, active)
        if not ok:
            return _json_error("Mahsulot topilmadi.", status=404)
        self.db.log_audit(auth["id"], "update_product", "products", pid, {"price": price, "cost": cost})
        return web.json_response({"ok": True, "product": self._serialize_product(self.db.get_product(pid))})

    async def superadmin_audit_logs(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        logs = [dict(r) for r in self.db.get_audit_logs(limit=100)]
        return web.json_response({"ok": True, "logs": logs})

    async def superadmin_export_csv(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        analytics = self.db.superadmin_analytics()
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["=== ECO PLATFORM · SUPERADMIN HISOBOTI ==="])
        writer.writerow(["Hisobot vaqti", db_now := Database.now_str() if hasattr(Database, "now_str") else ""])
        writer.writerow([])
        writer.writerow(["HUDUDLAR BO'YICHA TAQQOSLASH:"])
        writer.writerow(["Viloyat", "Diler", "Telefon", "Holat", "Ombor qoldig'i (dona)", "Buyurtmalar soni", "Savdo aylanmasi (so'm)", "Qarzdorlik (so'm)"])
        for r in analytics["regions_report"]:
            writer.writerow([r["region_name"], r["dealer_name"], r["dealer_phone"], r["status"], r["current_stock"], r["orders_count"], r["sales_revenue"], r["debt"]])

        writer.writerow([])
        writer.writerow(["MAHSULOTLAR SOTUV REYTINGI:"])
        writer.writerow(["Mahsulot nomi", "Sotilgan miqdor", "Jami tushum"])
        for p in analytics["products_ranking"]:
            writer.writerow([p["name"], p["sold_qty"], p["revenue"]])

        csv_content = output.getvalue()
        return web.Response(
            body=csv_content.encode("utf-8-sig"),
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="eco_hisobot.csv"'},
        )

    async def superadmin_list_orders(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        status = request.query.get("status")
        region_id = int(request.query["region_id"]) if request.query.get("region_id") else None
        limit = int(request.query.get("limit", 100))
        orders = self.db.list_orders(status=status, region_id=region_id, limit=limit)
        return web.json_response({
            "ok": True,
            "orders": [self._serialize_order(o) for o in orders]
        })

    async def superadmin_list_customers(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        region_id = int(request.query["region_id"]) if request.query.get("region_id") else None
        limit = int(request.query.get("limit", 100))
        users = self.db.users_list(limit=limit, region_id=region_id)
        return web.json_response({
            "ok": True,
            "customers": [dict(u) for u in users]
        })

    # ==================== DILER API (HUDUDIY BOSHQARUV) ====================
    async def dealer_overview(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        dealer = self.db.get_dealer(did)
        if not dealer:
            return _json_error("Diler topilmadi.", status=404)

        finance = self.db.get_dealer_finance_summary(did)
        inventory = [dict(r) for r in self.db.get_dealer_inventory(did)]
        pending_shipments = [dict(s) for s in self.db.list_shipments(dealer_id=did, status="shipped", limit=10)]
        recent_orders = [self._serialize_order(o) for o in self.db.list_orders(dealer_id=did, limit=20)]
        customers = [dict(u) for u in self.db.users_list(limit=50, region_id=dealer["region_id"])]

        return web.json_response(
            {
                "ok": True,
                "dealer": dict(dealer),
                "finance": finance,
                "inventory": inventory,
                "pending_shipments": pending_shipments,
                "recent_orders": recent_orders,
                "customers_count": len(customers),
            }
        )

    async def dealer_list_shipments(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        status_filter = request.query.get("status")
        shipments = []
        for s in self.db.list_shipments(dealer_id=did, status=status_filter, limit=50):
            d = dict(s)
            d["items"] = [dict(it) for it in self.db.get_shipment_items(s["id"])]
            shipments.append(d)
        return web.json_response({"ok": True, "shipments": shipments})

    async def dealer_confirm_shipment(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        shp_id = int(request.match_info["id"])
        try:
            data = await request.json()
            received_items = {int(k): int(v) for k, v in data.get("received_items", {}).items()}
            notes = str(data.get("notes", "")).strip()
        except Exception:
            return _json_error("Qabul ma'lumotlari to'g'ri kiritilmadi.")

        ok, result_status = self.db.confirm_shipment_receipt(
            shipment_id=shp_id,
            dealer_id=did,
            received_items=received_items,
            notes=notes,
            actor_id=auth["id"],
        )
        if not ok:
            return _json_error(result_status)

        # Tafovut bo'lsa SuperAdminga xabarnoma yuborish
        if result_status == "partial" and self.notify_discrepancy_cb:
            asyncio.create_task(self.notify_discrepancy_cb(shp_id, did, notes))

        return web.json_response({"ok": True, "status": result_status, "shipment": dict(self.db.get_shipment(shp_id))})

    async def dealer_inventory(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        inventory = [dict(r) for r in self.db.get_dealer_inventory(auth["dealer_id"])]
        return web.json_response({"ok": True, "inventory": inventory})

    async def dealer_orders(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        status_filter = request.query.get("status")
        q = request.query.get("q", "").strip()
        if q:
            orders = self.db.search_orders(q, dealer_id=did, limit=50)
        else:
            orders = self.db.list_orders(dealer_id=did, status=status_filter, limit=50)
        return web.json_response({"ok": True, "orders": [self._serialize_order(o) for o in orders]})

    async def dealer_set_order_status(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        oid = int(request.match_info["id"])
        try:
            data = await request.json()
            code = str(data.get("status", "")).strip()
        except Exception:
            return _json_error("Noto'g'ri so'rov.")

        if code not in FLOW:
            return _json_error("Noto'g'ri holat kodi.")

        o = self.db.get_order(oid)
        if not o:
            return _json_error("Buyurtma topilmadi.", status=404)

        # Agar diler bo'lsa, faqat o'z hududidagi buyurtmani o'zgartira oladi
        if not auth["is_superadmin"] and o["dealer_id"] != did:
            return _json_error("Bu buyurtma sizning hududingizga tegishli emas.", status=403)

        if o["status"] in FINAL:
            return _json_error("Yakunlangan yoki bekor qilingan buyurtma holatini o'zgartirib bo'lmaydi.")

        self.db.set_status(oid, code, actor_id=auth["id"])
        log.info("Buyurtma №%s holati o'zgardi: %s -> %s (kim: %s)", oid, o["status"], code, auth["id"])
        updated = self.db.get_order(oid)

        if self.notify_user_status_cb:
            asyncio.create_task(self.notify_user_status_cb(updated["user_id"], oid, code))

        return web.json_response({"ok": True, "order": self._serialize_order(updated)})

    async def dealer_customers(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        dealer = self.db.get_dealer(auth["dealer_id"])
        customers = [
            {
                "tg_id": u["tg_id"],
                "name": u["name"],
                "phone": u["phone"],
                "district": u["district"],
                "registered_at": u["registered_at"],
            }
            for u in self.db.users_list(limit=100, region_id=dealer["region_id"])
        ]
        return web.json_response({"ok": True, "customers": customers})

    async def dealer_finance(self, request: web.Request) -> web.Response:
        auth = self._require_dealer(request)
        did = auth["dealer_id"]
        summary = self.db.get_dealer_finance_summary(did)
        ledger = [dict(r) for r in self.db.get_dealer_ledger(did, limit=50)]
        return web.json_response({"ok": True, "summary": summary, "ledger": ledger})

    # ==================== LEGACY ADMIN COMPATIBILITY ====================
    async def admin_overview(self, request: web.Request) -> web.Response:
        auth = self._require_any_admin(request)
        if auth["is_superadmin"]:
            return await self.superadmin_overview(request)
        elif auth["is_dealer"]:
            return await self.dealer_overview(request)
        return _json_error("Ruxsat yo'q.", status=403)

    async def admin_set_order_status(self, request: web.Request) -> web.Response:
        return await self.dealer_set_order_status(request)

    async def admin_toggle_product(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        pid = int(request.match_info["id"])
        self.db.toggle_product(pid)
        return web.json_response(
            {"ok": True, "products": [self._serialize_product(p) for p in self.db.products(active_only=False)]}
        )

    async def admin_set_product_price(self, request: web.Request) -> web.Response:
        self._require_superadmin(request)
        pid = int(request.match_info["id"])
        data = await request.json()
        price = int(data["price"])
        self.db.set_price_by_id(pid, price)
        return web.json_response(
            {"ok": True, "products": [self._serialize_product(p) for p in self.db.products(active_only=False)]}
        )


@web.middleware
async def speed_middleware(request: web.Request, handler):
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    }
    if request.method == "OPTIONS":
        return web.Response(status=200, headers=cors_headers)
    resp = await handler(request)
    try:
        resp.enable_compression()
    except Exception:
        pass
    resp.headers.update(cors_headers)
    path = request.path
    if path.startswith("/images/"):
        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    elif path.startswith("/static/"):
        if "app.js" in path:
            resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        else:
            resp.headers["Cache-Control"] = "public, max-age=86400"
    elif path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


def create_webapp(
    db: Database,
    notify_admins_cb: NotifyAdminsCb | None = None,
    notify_dealer_cb: NotifyDealerCb | None = None,
    notify_user_status_cb: NotifyUserStatusCb | None = None,
    notify_discrepancy_cb: NotifyDiscrepancyCb | None = None,
) -> web.Application:
    app = web.Application(middlewares=[speed_middleware])
    h = WebAppHandler(
        db,
        notify_admins_cb=notify_admins_cb,
        notify_dealer_cb=notify_dealer_cb,
        notify_user_status_cb=notify_user_status_cb,
        notify_discrepancy_cb=notify_discrepancy_cb,
    )

    # Statik va umumiy
    app.router.add_get("/", h.index)
    app.router.add_get("/api/health", h.health)
    app.router.add_get("/api/regions", h.get_regions_list)
    app.router.add_get("/api/bootstrap", h.bootstrap)
    app.router.add_post("/api/age-confirm", h.age_confirm)
    app.router.add_post("/api/register", h.register_user)
    app.router.add_post("/api/user/region", h.save_user_region)
    app.router.add_post("/api/cart", h.set_cart_item)
    app.router.add_delete("/api/cart", h.clear_cart)
    app.router.add_get("/api/orders", h.list_my_orders)
    app.router.add_post("/api/orders", h.create_order)

    # SuperAdmin (Zavod) API
    app.router.add_get("/api/superadmin/overview", h.superadmin_overview)
    app.router.add_get("/api/superadmin/dealers", h.superadmin_get_dealers)
    app.router.add_post("/api/superadmin/dealers", h.superadmin_save_dealer)
    app.router.add_post("/api/superadmin/dealers/{id}/status", h.superadmin_set_dealer_status)
    app.router.add_delete("/api/superadmin/dealers/{id}", h.superadmin_delete_dealer)
    app.router.add_get("/api/superadmin/factory/inventory", h.superadmin_factory_inventory)
    app.router.add_post("/api/superadmin/factory/inventory/adjust", h.superadmin_adjust_factory_inventory)
    app.router.add_get("/api/superadmin/shipments", h.superadmin_list_shipments)
    app.router.add_post("/api/superadmin/shipments", h.superadmin_create_shipment)
    app.router.add_get("/api/superadmin/dealers/{id}/finance", h.superadmin_dealer_finance)
    app.router.add_post("/api/superadmin/dealers/{id}/payments", h.superadmin_record_dealer_payment)
    app.router.add_get("/api/superadmin/products", h.superadmin_manage_products)
    app.router.add_post("/api/superadmin/products", h.superadmin_create_product)
    app.router.add_post("/api/superadmin/products/{id}/update", h.superadmin_update_product)
    app.router.add_get("/api/superadmin/orders", h.superadmin_list_orders)
    app.router.add_get("/api/superadmin/customers", h.superadmin_list_customers)
    app.router.add_get("/api/superadmin/audit", h.superadmin_audit_logs)
    app.router.add_get("/api/superadmin/export", h.superadmin_export_csv)

    # Dealer (Hududiy Diler) API
    app.router.add_get("/api/dealer/overview", h.dealer_overview)
    app.router.add_get("/api/dealer/shipments", h.dealer_list_shipments)
    app.router.add_post("/api/dealer/shipments/{id}/confirm", h.dealer_confirm_shipment)
    app.router.add_get("/api/dealer/inventory", h.dealer_inventory)
    app.router.add_get("/api/dealer/orders", h.dealer_orders)
    app.router.add_post("/api/dealer/orders/{id}/status", h.dealer_set_order_status)
    app.router.add_get("/api/dealer/customers", h.dealer_customers)
    app.router.add_get("/api/dealer/finance", h.dealer_finance)

    # Eski admin marshrutlari mosligi
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
